# theC64 Maxi — Sega Genesis 6-Button USB Adapter
### Raspberry Pi Pico · MicroPython

This adapter lets you use a Sega Genesis / Mega Drive 6-button controller with
**theC64 Maxi** retro computer. The Pico reads the Genesis pad over its DB9
connector and presents itself to the C64 Maxi via USB as an exact clone of the
official theC64 joystick.

---

## Hardware Required

| Item | Notes |
|------|-------|
| Raspberry Pi Pico | Standard or Pico W — USB-capable |
| DE-9 (DB9) female socket | Mounts on the case; connects to Genesis pad |
| USB-A cable / connector | Pico micro-USB → C64 Maxi USB port |
| 10× 1kΩ resistors (optional) | Series protection on input lines — simpler build |
| 74AHCT245 level shifter (optional) | Cleaner 5V→3.3V translation — recommended for permanent builds |
| Small enclosure | Any project box |

---

## Wiring

![Raspberry Pi Pico GPIO pinout — THEC64 to Genesis wiring](images/Raspberry%20Pi%20Pico%20GPIO%20pins%20THEC64%20to%20Genny.png)

> **Pinout diagram:** [`images/Raspberry Pi Pico GPIO pins THEC64 to Genny.png`](images/Raspberry%20Pi%20Pico%20GPIO%20pins%20THEC64%20to%20Genny.png) (raster) · [`images/Raspberry Pi Pico GPIO pins THEC64 to Genny.svg`](images/Raspberry%20Pi%20Pico%20GPIO%20pins%20THEC64%20to%20Genny.svg) (scalable/printable)

Only **7 GPIO pins** are needed. The Genesis 6-button controller multiplexes
all 12 inputs over 6 data wires — the direction pins (DB9:1-4) double as
the 6-button extra pins (Z/Y/X/Mode) on the 3rd SELECT=HIGH cycle.

### Genesis DB9 Female Socket → Pico GPIO

```
Genesis DB9 Pin   Signal (multiplexed)              Pico GPIO / Power
────────────────────────────────────────────────────────────────────────
   1              Up  (normal cycles) / Z (6-btn★)  GP2   (Pin 4)
   2              Down               / Y (6-btn★)   GP3   (Pin 5)
   3              Left               / X (6-btn★)   GP4   (Pin 6)
   4              Right              / Mode (6-btn★) GP5  (Pin 7)
   5              +5V                                VBUS  (Pin 40)
   6              B=Fire (SELECT-HIGH) / A=Jump (LOW) GP6 (Pin 9)
   7              SELECT strobe                       GP14 (Pin 19) ← OUTPUT
   8              GND                                GND   (Pin 38)
   9              C=Space (SELECT-HIGH) / Start (LOW) GP7 (Pin 10)

★ DB9 pins 1-4 carry Z/Y/X/Mode instead of directions on the
  3rd SELECT=HIGH cycle. The firmware reads them at the right moment.
```

> **Important:** Genesis controllers use +5V logic. The Pico is 3.3V.
> Add a 1kΩ series resistor on each input signal line (DB9 pins 1-4, 6, 9)
> as a simple current limiter. For a more robust build use a 74AHCT245
> level shifter on the input lines (not the SELECT output line).

### SELECT line timing
The firmware drives GP14 through a 7-transition sequence (4 LOW, 3 HIGH)
per read cycle to clock the controller's internal multiplexer. The 3rd
HIGH transition triggers the 6-button extra buttons on DB9 pins 1-4. A
final LOW resets the counter ready for the next read.

---

## Button Mapping

| Genesis Button | theC64 Function      | Notes |
|----------------|----------------------|-------|
| D-Pad          | Joystick directions  | Normal movement |
| **B**          | **Fire (primary)**   | **Reserved — main fire button** |
| **A**          | **Jump / Up**        | **Reserved — sends joystick-up + Button 2** |
| C              | Space bar            | Secondary action / weapon select |
| Y              | Return / Enter       | Menu confirm, text input |
| X              | Menu Select (A btn)  | Navigate C64 menus |
| Z              | Menu Back / Escape   | Go back in menus |
| Start          | Restore (NMI)        | Opens the C64 Maxi game menu |
| Mode           | (unassigned)         | Edit firmware to customise |

### Why B=Fire and A=Jump?
Holding the Genesis pad naturally, **B** sits directly under your right thumb —
the same ergonomic position as the single fire button on a classic Atari/C64
joystick. **A** is one step left and equally reachable for rapid jump+fire
combos. Pressing **A** simultaneously asserts both the Up axis AND Button 2,
covering all C64 games regardless of whether they test the joystick axis or
the button for jumping.

---

## Software Setup

### Option A (recommended): CircuitPython HID

Use this option if your MicroPython build does not provide `usb.device`.

1. **Flash CircuitPython** for Raspberry Pi Pico.
   Download from: https://circuitpython.org/board/raspberry_pi_pico/

2. **Copy both firmware files** from this repo to the root of the CIRCUITPY drive:
   - `circuitpython/boot.py` -> `/boot.py`
   - `circuitpython/code.py` -> `/code.py`

3. **Power-cycle or reset** the Pico after copying `boot.py`.
   USB HID descriptors are loaded at boot, so this reset is required.

4. **Connect and test:**
   - Plug the Pico into the C64 Maxi's USB port.
   - The C64 Maxi should detect it as a joystick device.
   - No driver installation needed.

#### CircuitPython live debug mode (optional)

If you want to verify wiring and button reads in real time:

1. Open `circuitpython/code.py` and set `DEBUG_SERIAL = True`.
2. Keep the default `DEBUG_PRINT_INTERVAL_MS = 75` (or increase it to reduce logs).
3. Open the CircuitPython serial console (`/dev/ttyACM*` on Linux).
4. Press buttons and D-pad directions.

You will see lines like:
```
GEN buttons=left,b | report=(x=-127, y=0, bits=0b00000001)
```

Meaning:
- `buttons=` shows raw Genesis inputs currently detected.
- `report=` shows exactly what HID packet is being sent to theC64.

#### CircuitPython raw pin-phase debug (wiring diagnostics)

To inspect raw line levels during each SELECT phase:

1. In `circuitpython/code.py`, set both:
   - `DEBUG_SERIAL = True`
   - `DEBUG_RAW_PHASES = True`
2. Keep `DEBUG_RAW_PRINT_INTERVAL_MS = 120` or raise it if output is too fast.
3. Watch for lines like:
```
RAW p[1,2,3,4,6,9] L1:[1,1,1,1,0,1] H1:[1,1,1,1,1,1] L2:[1,1,1,1,0,1] H2:[1,1,1,1,1,1] L3:[1,1,1,1,0,1] H3:[1,1,1,1,1,1] L4:[1,1,1,1,0,1]
```

How to read it:
- `p[1,2,3,4,6,9]` means DB9 pins sampled in that order.
- Each phase block (`L1`, `H1`, `L2`, `H2`, `L3`, `H3`, `L4`) corresponds to the SELECT sequence.
- Values are active-low: `0 = asserted/pressed`, `1 = released`.
- For example, pressing `B` should usually drive DB9 pin 6 low on HIGH phases (`H1/H2/H3`).
- Pressing `A` should usually drive DB9 pin 6 low on LOW phases (`L1/L2/L3/L4`).

### Option B: MicroPython usb.device HID

1. **Flash MicroPython with USB device support** onto the Pico.
   Some builds do not include `usb.device`. Verify in REPL:
   - `import usb`
   - `import usb.device`
   - `from usb.device.hid import HIDInterface`

2. **Copy the MicroPython firmware** to the Pico:
   ```
   mpremote cp c64_genesis_adapter.py :main.py
   ```

3. **Connect and test:**
   - Plug the Pico into the C64 Maxi's USB port.
   - The C64 Maxi should detect it as "theC64 Joystick" automatically.
   - No driver installation needed.

---

## Customising the Mapping

Edit the `genesis_to_c64()` function in `c64_genesis_adapter.py`.

Button bit positions:
```
bit 0  →  Button 1  =  Fire (primary)
bit 1  →  Button 2  =  Up/Jump
bit 2  →  Button 3  =  Space
bit 3  →  Button 4  =  Return
bit 4  →  Button 5  =  Menu Select
bit 5  →  Button 6  =  Menu Back
bit 6  →  Button 7  =  Restore / NMI
```

To reassign a button, change which genesis key sets which bit.

---

## GPIO Pin Reassignment

Change the `PIN_DB9_*` assignments near the top of `c64_genesis_adapter.py`
to match your physical wiring. Any GPIO pins can be used — just update the
numbers.

---

## Schematic Notes

Genesis signals are active-low (pressed = 0V). The Pico's internal pull-ups
hold unconnected/released lines HIGH.

There are two ways to protect the Pico from the Genesis controller's 5V logic.
Pick whichever suits your build:

### Option A — 1kΩ resistors (quick & simple)

Drop one resistor in series on each of the 6 data lines. That's it.

```
Genesis DB9 pin ──[1kΩ]──── Pico GPIO (input, internal pull-up enabled)
Genesis +5V (pin 5) ──────── Pico VBUS
Genesis GND (pin 8) ──────── Pico GND
Pico GP14 ────────────────── Genesis SELECT (DB9 pin 7)   ← no resistor needed
```

Good for breadboard prototyping. Not as clean electrically, but works fine.

---

### Option B — 74AHCT245 level shifter (recommended for permanent builds)

The 74AHCT245 is an 8-channel buffer/transceiver. Its A-side inputs are
5V-tolerant even when the chip itself runs on 3.3V, so it neatly converts
the Genesis 5V signals down to safe 3.3V levels for the Pico. No resistors
needed on the data lines.

#### How the chip works (in plain English)

- Power it from the Pico's **3.3V rail**, not 5V.
- Signals enter on the **A side** (5V from the Genesis) and come out on the
  **B side** (3.3V, safe for the Pico).
- **DIR pin HIGH** = data flows A → B (that's always what we want here).
- **!OE pin LOW** = chip is active (tie it to GND permanently).
- The SELECT output line (Pico → Genesis) bypasses the chip entirely — the
  Genesis is happy with 3.3V on that line.

#### Wiring table

| 74AHCT245 Pin | Name | Connect to |
|---|---|---|
| 20 | VCC | Pico pin 36 (3.3V OUT) |
| 10 | GND | Pico GND |
| 1 | DIR | Pico 3.3V (tie HIGH — A→B direction always) |
| 19 | !OE | GND (tie LOW — always enabled) |
| 2 | A1 | Genesis DB9 pin 1 (Up / Z) |
| 3 | A2 | Genesis DB9 pin 2 (Down / Y) |
| 4 | A3 | Genesis DB9 pin 3 (Left / X) |
| 5 | A4 | Genesis DB9 pin 4 (Right / Mode) |
| 6 | A5 | Genesis DB9 pin 6 (B / A) |
| 7 | A6 | Genesis DB9 pin 9 (C / Start) |
| 8–9 | A7, A8 | Unused — leave floating |
| 18 | B1 | Pico GP2 (pin 4) |
| 17 | B2 | Pico GP3 (pin 5) |
| 16 | B3 | Pico GP4 (pin 6) |
| 15 | B4 | Pico GP5 (pin 7) |
| 14 | B5 | Pico GP6 (pin 9) |
| 13 | B6 | Pico GP7 (pin 10) |

#### Signal flow diagram

```
                    74AHCT245  (VCC = 3.3V)
                  ┌─────────────────────┐
Genesis DB9 pin 1 ─── A1          B1 ───── Pico GP2
Genesis DB9 pin 2 ─── A2          B2 ───── Pico GP3
Genesis DB9 pin 3 ─── A3          B3 ───── Pico GP4
Genesis DB9 pin 4 ─── A4          B4 ───── Pico GP5
Genesis DB9 pin 6 ─── A5          B5 ───── Pico GP6
Genesis DB9 pin 9 ─── A6          B6 ───── Pico GP7
         3.3V ──────── DIR       !OE ───── GND
                  └─────────────────────┘

Genesis DB9 pin 5 (+5V) ──────────────────── Pico VBUS (pin 40)
Genesis DB9 pin 8 (GND) ──────────────────── Pico GND
Pico GP14 (pin 19) ────────────────────────── Genesis DB9 pin 7 (SELECT)
```

> **Tip:** Place a **100 nF ceramic capacitor** between pin 20 (VCC) and
> pin 10 (GND) as close to the chip as possible. This decoupling cap
> suppresses switching noise and is standard good practice on any IC.

With the 74AHCT245 in place you do **not** need the 1kΩ resistors on the
data lines — the chip handles everything.

---

## Files

| File | Description |
|------|-------------|
| `c64_genesis_adapter.py` | MicroPython firmware — copy to Pico as `main.py` |
| `circuitpython/boot.py` | CircuitPython USB HID descriptor setup (must be copied as `/boot.py`) |
| `circuitpython/code.py` | CircuitPython runtime firmware (copy as `/code.py`) |
| `BUTTON_MAPPING.md` | Detailed button mapping reference |
| `README.md` | This file |
| `images/Raspberry Pi Pico GPIO pins THEC64 to Genny.png` | Pinout/wiring diagram (raster) |
| `images/Raspberry Pi Pico GPIO pins THEC64 to Genny.svg` | Pinout/wiring diagram (scalable/printable) |
