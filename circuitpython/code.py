"""
CircuitPython firmware
USB -> 9-pin DB9 adapter: Sega Genesis 6-button pad -> theC64 Maxi

Requires circuitpython/boot.py to be copied as /boot.py so the custom
USB HID descriptor is enabled before enumeration.
"""

import time
import board
import digitalio
import microcontroller
import usb_hid

SELECT_SETTLE_US = 20
SELECT_RESET_US = 1500

# Set True to print controller state changes to the serial console.
DEBUG_SERIAL = False
DEBUG_PRINT_INTERVAL_MS = 75

# Set True to also print raw DB9 pin levels for each SELECT phase.
# Raw values are active-low: 0 means pressed/asserted, 1 means released.
DEBUG_RAW_PHASES = False
DEBUG_RAW_PRINT_INTERVAL_MS = 120


def make_input(pin):
    p = digitalio.DigitalInOut(pin)
    p.direction = digitalio.Direction.INPUT
    p.pull = digitalio.Pull.UP
    return p


PIN_DB9_1 = make_input(board.GP2)  # Up / Z
PIN_DB9_2 = make_input(board.GP3)  # Down / Y
PIN_DB9_3 = make_input(board.GP4)  # Left / X
PIN_DB9_4 = make_input(board.GP5)  # Right / Mode
PIN_DB9_6 = make_input(board.GP6)  # B (HIGH) / A (LOW)
PIN_DB9_9 = make_input(board.GP7)  # C (HIGH) / Start (LOW)

PIN_SELECT = digitalio.DigitalInOut(board.GP14)
PIN_SELECT.direction = digitalio.Direction.OUTPUT
PIN_SELECT.value = False


def _delay_us(us):
    microcontroller.delay_us(us)


def _pulse_select(state):
    PIN_SELECT.value = bool(state)
    _delay_us(SELECT_SETTLE_US)


def _reset_select_counter():
    PIN_SELECT.value = False
    _delay_us(SELECT_RESET_US)


def _pressed(pin):
    return not pin.value  # Active low


def _raw_levels_tuple():
    # Order: DB9 pins 1,2,3,4,6,9
    return (
        int(PIN_DB9_1.value),
        int(PIN_DB9_2.value),
        int(PIN_DB9_3.value),
        int(PIN_DB9_4.value),
        int(PIN_DB9_6.value),
        int(PIN_DB9_9.value),
    )


def read_genesis_6btn(capture_raw=False):
    state = {
        "up": False,
        "down": False,
        "left": False,
        "right": False,
        "a": False,
        "b": False,
        "c": False,
        "x": False,
        "y": False,
        "z": False,
        "start": False,
        "mode": False,
    }

    raw = None
    if capture_raw:
        raw = {}

    _reset_select_counter()

    # 1st LOW
    if capture_raw:
        raw["l1"] = _raw_levels_tuple()
    state["a"] = _pressed(PIN_DB9_6)
    state["start"] = _pressed(PIN_DB9_9)
    state["up"] = _pressed(PIN_DB9_1)
    state["down"] = _pressed(PIN_DB9_2)

    # 1st HIGH
    _pulse_select(True)
    if capture_raw:
        raw["h1"] = _raw_levels_tuple()
    state["up"] = _pressed(PIN_DB9_1)
    state["down"] = _pressed(PIN_DB9_2)
    state["left"] = _pressed(PIN_DB9_3)
    state["right"] = _pressed(PIN_DB9_4)
    state["b"] = _pressed(PIN_DB9_6)
    state["c"] = _pressed(PIN_DB9_9)

    # 2nd LOW/HIGH
    _pulse_select(False)
    if capture_raw:
        raw["l2"] = _raw_levels_tuple()
    _pulse_select(True)
    if capture_raw:
        raw["h2"] = _raw_levels_tuple()

    # 3rd LOW/HIGH: Z/Y/X/Mode on pins 1-4
    _pulse_select(False)
    if capture_raw:
        raw["l3"] = _raw_levels_tuple()
    _pulse_select(True)
    if capture_raw:
        raw["h3"] = _raw_levels_tuple()
    state["z"] = _pressed(PIN_DB9_1)
    state["y"] = _pressed(PIN_DB9_2)
    state["x"] = _pressed(PIN_DB9_3)
    state["mode"] = _pressed(PIN_DB9_4)

    _pulse_select(False)
    if capture_raw:
        raw["l4"] = _raw_levels_tuple()
    _reset_select_counter()

    if capture_raw:
        return state, raw
    return state


def genesis_to_c64(genesis):
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

    # A button sends both jump button and Y-up.
    if genesis["a"]:
        y = -127

    buttons = 0
    if genesis["b"]:
        buttons |= 1 << 0  # Fire
    if genesis["a"]:
        buttons |= 1 << 1  # Jump/Up
    if genesis["c"]:
        buttons |= 1 << 2  # Space
    if genesis["y"]:
        buttons |= 1 << 3  # Return
    if genesis["x"]:
        buttons |= 1 << 4  # Menu select
    if genesis["z"]:
        buttons |= 1 << 5  # Menu back
    if genesis["start"]:
        buttons |= 1 << 6  # Restore

    return x, y, buttons


def clamp_int8(v):
    if v < -127:
        return -127
    if v > 127:
        return 127
    return int(v)


def int8_to_u8(v):
    return clamp_int8(v) & 0xFF


def find_thec64_hid_device():
    # boot.py enables only one HID device, so use the first one.
    if not usb_hid.devices:
        raise RuntimeError("No USB HID devices are enabled. Check boot.py.")
    return usb_hid.devices[0]


def send_state(hid_dev, x, y, buttons):
    report = bytes((int8_to_u8(x), int8_to_u8(y), buttons & 0xFF))
    hid_dev.send_report(report)


def _active_buttons_text(genesis):
    order = ("up", "down", "left", "right", "a", "b", "c", "x", "y", "z", "start", "mode")
    active = [name for name in order if genesis[name]]
    return ",".join(active) if active else "none"


def _raw_phase_text(raw):
    phase_order = ("l1", "h1", "l2", "h2", "l3", "h3", "l4")
    labels = {
        "l1": "L1",
        "h1": "H1",
        "l2": "L2",
        "h2": "H2",
        "l3": "L3",
        "h3": "H3",
        "l4": "L4",
    }
    chunks = []
    for key in phase_order:
        lv = raw[key]
        chunks.append(
            "{0}:[{1},{2},{3},{4},{5},{6}]".format(
                labels[key], lv[0], lv[1], lv[2], lv[3], lv[4], lv[5]
            )
        )
    return " ".join(chunks)


def main():
    hid_dev = find_thec64_hid_device()
    print("theC64 Genesis Adapter (CircuitPython) running")

    _reset_select_counter()
    last_report = None
    last_genesis = None
    last_debug_ms = 0
    last_raw = None
    last_raw_debug_ms = 0

    while True:
        if DEBUG_RAW_PHASES:
            genesis, raw = read_genesis_6btn(capture_raw=True)
        else:
            genesis = read_genesis_6btn()
            raw = None
        report = genesis_to_c64(genesis)

        if DEBUG_SERIAL:
            now = time.monotonic_ns() // 1000000
            genesis_tuple = tuple(genesis[k] for k in ("up", "down", "left", "right", "a", "b", "c", "x", "y", "z", "start", "mode"))
            changed = genesis_tuple != last_genesis
            if changed and (now - last_debug_ms) >= DEBUG_PRINT_INTERVAL_MS:
                print(
                    "GEN buttons={0} | report=(x={1}, y={2}, bits=0b{3:08b})".format(
                        _active_buttons_text(genesis), report[0], report[1], report[2]
                    )
                )
                last_debug_ms = now
            last_genesis = genesis_tuple

            if DEBUG_RAW_PHASES and raw is not None:
                raw_tuple = tuple(raw[k] for k in ("l1", "h1", "l2", "h2", "l3", "h3", "l4"))
                raw_changed = raw_tuple != last_raw
                if raw_changed and (now - last_raw_debug_ms) >= DEBUG_RAW_PRINT_INTERVAL_MS:
                    print("RAW p[1,2,3,4,6,9] {0}".format(_raw_phase_text(raw)))
                    last_raw_debug_ms = now
                last_raw = raw_tuple

        if report != last_report:
            send_state(hid_dev, report[0], report[1], report[2])
            last_report = report

        time.sleep(0.0005)


main()
