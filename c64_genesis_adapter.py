"""
c64_genesis_adapter.py
======================
Raspberry Pi Pico MicroPython firmware
USB → 9-pin DB9 adapter: Sega Genesis 6-button pad → theC64 Maxi

Presents as a USB HID device that exactly mimics the official theC64
joystick HID descriptor so the C64 Maxi recognises it natively.

Button mapping:
  Genesis B      → Fire (Button 1)           [RESERVED]
  Genesis A      → Jump/Up (Button 2 + Y-up) [RESERVED]
  Genesis C      → Space (Button 3)
  Genesis Y      → Return (Button 4)
  Genesis X      → Menu select (Button 5)
  Genesis Z      → Menu back (Button 6)
  Genesis Start  → Restore/NMI (Button 7)
  D-Pad          → Joystick axes (X/Y)

Wiring — only 7 GPIO pins needed (see README.md for full table):
  DB9 pin 1 → GP2   (Up on normal cycles / Z on 3rd SELECT-HIGH cycle)
  DB9 pin 2 → GP3   (Down / Y)
  DB9 pin 3 → GP4   (Left / X)
  DB9 pin 4 → GP5   (Right / Mode)
  DB9 pin 6 → GP6   (B=Fire on SELECT-HIGH / A=Jump on SELECT-LOW)
  DB9 pin 9 → GP7   (C=Space on SELECT-HIGH / Start=Restore on SELECT-LOW)
  DB9 pin 7 ← GP14  (SELECT strobe output from Pico)
  DB9 pin 5 →  VBUS (+5V)
  DB9 pin 8 →  GND

NOTE: The Genesis 6-button controller multiplexes all 12 inputs over 9 pins
using the SELECT line.  Pins 1-4 carry direction inputs on normal SELECT
cycles but switch to Z/Y/X/Mode on the 3rd SELECT=HIGH pulse in a read
sequence.  Pin 6 carries B on HIGH and A on LOW.  Pin 9 carries C on HIGH
and Start on LOW.  We therefore need only 6 data GPIO pins (GP2-GP7) plus
the SELECT output (GP14) — not 13 separate pins.
"""

import time
import usb.device
from usb.device.hid import HIDInterface

# ---------------------------------------------------------------------------
# GPIO pin assignments  (change these to match your wiring)
# ---------------------------------------------------------------------------
from machine import Pin

# Each name reflects which DB9 pin the signal comes from.
# The multiplexing protocol determines WHICH signal is active at read time.
PIN_DB9_1 = Pin(2,  Pin.IN, Pin.PULL_UP)   # DB9 pin 1: Up  / Z (6-btn 3rd HIGH)
PIN_DB9_2 = Pin(3,  Pin.IN, Pin.PULL_UP)   # DB9 pin 2: Down / Y
PIN_DB9_3 = Pin(4,  Pin.IN, Pin.PULL_UP)   # DB9 pin 3: Left / X
PIN_DB9_4 = Pin(5,  Pin.IN, Pin.PULL_UP)   # DB9 pin 4: Right / Mode
PIN_DB9_6 = Pin(6,  Pin.IN, Pin.PULL_UP)   # DB9 pin 6: B (SELECT-HIGH) / A (SELECT-LOW)
PIN_DB9_9 = Pin(7,  Pin.IN, Pin.PULL_UP)   # DB9 pin 9: C (SELECT-HIGH) / Start (SELECT-LOW)

# SELECT strobe output — drives DB9 pin 7
PIN_SELECT = Pin(14, Pin.OUT)

# ---------------------------------------------------------------------------
# HID descriptor — mirrors theC64 joystick exactly
#
# Report layout (3 bytes):
#   Byte 0:  X axis  (int8, -127..127)
#   Byte 1:  Y axis  (int8, -127..127)
#   Byte 2:  Buttons b0-b6 (bits 0..6 = buttons 1..7)
# ---------------------------------------------------------------------------
HID_REPORT_DESCRIPTOR = bytes([
    0x05, 0x01,        # Usage Page (Generic Desktop)
    0x09, 0x04,        # Usage (Joystick)
    0xA1, 0x01,        # Collection (Application)

    # --- Axes ---
    0x09, 0x30,        #   Usage (X)
    0x09, 0x31,        #   Usage (Y)
    0x15, 0x81,        #   Logical Minimum (-127)
    0x25, 0x7F,        #   Logical Maximum (127)
    0x75, 0x08,        #   Report Size (8)
    0x95, 0x02,        #   Report Count (2)
    0x81, 0x02,        #   Input (Data, Var, Abs)

    # --- 7 Buttons ---
    0x05, 0x09,        #   Usage Page (Button)
    0x19, 0x01,        #   Usage Minimum (Button 1)
    0x29, 0x07,        #   Usage Maximum (Button 7)
    0x15, 0x00,        #   Logical Minimum (0)
    0x25, 0x01,        #   Logical Maximum (1)
    0x75, 0x01,        #   Report Size (1)
    0x95, 0x07,        #   Report Count (7)
    0x81, 0x02,        #   Input (Data, Var, Abs)

    # --- 1 padding bit ---
    0x75, 0x01,        #   Report Size (1)
    0x95, 0x01,        #   Report Count (1)
    0x81, 0x03,        #   Input (Const, Var, Abs)

    0xC0               # End Collection
])


class C64JoystickHID(HIDInterface):
    """USB HID interface that looks like the official theC64 joystick."""

    def __init__(self):
        super().__init__(
            HID_REPORT_DESCRIPTOR,
            set_report_buf=None,
            protocol=0,        # None / undefined
            interface_str="theC64 Joystick",
        )
        self._report = bytearray(3)   # x, y, buttons

    def send_state(self, x: int, y: int, buttons: int):
        """
        x, y   : -127..127
        buttons: bitmask, bit 0 = Button1 (Fire), bit 6 = Button7 (Restore)
        """
        self._report[0] = x & 0xFF
        self._report[1] = y & 0xFF
        self._report[2] = buttons & 0xFF
        self.send_report(self._report)


# ---------------------------------------------------------------------------
# Genesis 6-button read logic
# ---------------------------------------------------------------------------

def _pulse_select(state: bool):
    PIN_SELECT.value(1 if state else 0)
    time.sleep_us(20)   # ≥20 µs settling time


def read_genesis_6btn() -> dict:
    """
    Read a full Genesis 6-button controller state via SELECT strobing.

    The Genesis 6-button controller multiplexes 12 inputs over 6 data wires
    using the SELECT line (DB9 pin 7).  The Pico drives SELECT; the controller
    has an internal counter that increments on each SELECT=HIGH transition.

    Multiplexing table:
      Cycle          DB9:1  DB9:2  DB9:3  DB9:4  DB9:6  DB9:9
      ─────────────────────────────────────────────────────────
      1st LOW        Up     Down   GND    GND    A      Start
      1st HIGH       Up     Down   Left   Right  B      C
      2nd LOW        Up     Down   GND    GND    A      Start
      2nd HIGH       Up     Down   Left   Right  B      C
      3rd LOW        Up     Down   GND    GND    A      Start
      3rd HIGH ★     Z      Y      X      Mode   B      C      ← 6-btn extra
      4th LOW        Up     Down   GND    GND    A      Start  (reset)

    ★ = the 3rd SELECT=HIGH is the 6-button special cycle.

    Returns a dict:
      up, down, left, right, a, b, c, x, y, z, start, mode  → bool (True = pressed)
    """
    state = {k: False for k in ("up","down","left","right","a","b","c","x","y","z","start","mode")}

    # --- 1st LOW: read A and Start from DB9 pins 6 and 9 ---
    _pulse_select(False)
    state["a"]     = not PIN_DB9_6.value()
    state["start"] = not PIN_DB9_9.value()
    # Up/Down also valid here; overwritten below from HIGH cycle
    state["up"]    = not PIN_DB9_1.value()
    state["down"]  = not PIN_DB9_2.value()

    # --- 1st HIGH: read Up/Down/Left/Right + B/C ---
    _pulse_select(True)
    state["up"]    = not PIN_DB9_1.value()
    state["down"]  = not PIN_DB9_2.value()
    state["left"]  = not PIN_DB9_3.value()
    state["right"] = not PIN_DB9_4.value()
    state["b"]     = not PIN_DB9_6.value()
    state["c"]     = not PIN_DB9_9.value()

    # --- 2nd LOW / 2nd HIGH: no new data, just clock the counter ---
    _pulse_select(False)
    _pulse_select(True)

    # --- 3rd LOW ---
    _pulse_select(False)

    # --- 3rd HIGH ★: 6-button extra buttons on pins 1-4 ---
    _pulse_select(True)
    state["z"]    = not PIN_DB9_1.value()
    state["y"]    = not PIN_DB9_2.value()
    state["x"]    = not PIN_DB9_3.value()
    state["mode"] = not PIN_DB9_4.value()

    # --- 4th LOW: reset controller's internal counter ---
    _pulse_select(False)

    return state


def genesis_to_c64(genesis: dict) -> tuple:
    """
    Convert a Genesis state dict to (x, y, buttons) for the C64 HID report.

    Button bit layout (byte 2 of report):
      bit 0 = Button 1 = Fire        ← Genesis B  [RESERVED]
      bit 1 = Button 2 = Up/Jump     ← Genesis A  [RESERVED]  also pulses Y-up
      bit 2 = Button 3 = Space       ← Genesis C
      bit 3 = Button 4 = Return      ← Genesis Y
      bit 4 = Button 5 = Menu Select ← Genesis X
      bit 5 = Button 6 = Menu Back   ← Genesis Z
      bit 6 = Button 7 = Restore     ← Genesis Start
    """
    # Axes
    x = 0
    y = 0

    if genesis["left"]:
        x = -127
    elif genesis["right"]:
        x = 127

    if genesis["up"]:
        y = -127
    elif genesis["down"]:
        y = 127

    # "A" button = Jump: assert Y-up AND Button 2 simultaneously
    if genesis["a"]:
        y = -127   # override axis to up

    # Button bitmask
    buttons = 0
    if genesis["b"]:        buttons |= (1 << 0)   # Fire
    if genesis["a"]:        buttons |= (1 << 1)   # Jump (+ axis already set above)
    if genesis["c"]:        buttons |= (1 << 2)   # Space
    if genesis["y"]:        buttons |= (1 << 3)   # Return
    if genesis["x"]:        buttons |= (1 << 4)   # Menu select
    if genesis["z"]:        buttons |= (1 << 5)   # Menu back
    if genesis["start"]:    buttons |= (1 << 6)   # Restore

    return (x, y, buttons)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    hid = C64JoystickHID()

    # Register the HID device and enable USB
    usb.device.get().init(hid, builtin_driver=True)

    print("theC64 Genesis Adapter — waiting for USB enumeration...")

    # Wait until the host has enumerated us
    while not hid.is_open():
        time.sleep_ms(10)

    print("USB connected — entering main loop")

    last_report = None

    while True:
        genesis = read_genesis_6btn()
        x, y, buttons = genesis_to_c64(genesis)

        report = (x, y, buttons)
        if report != last_report:
            hid.send_state(x, y, buttons)
            last_report = report

        time.sleep_us(500)   # ~2 kHz poll rate — well within USB HID limits


if __name__ == "__main__":
    main()
