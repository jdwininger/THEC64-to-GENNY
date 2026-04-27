# Button Mapping: Sega Genesis 6-Button → theC64 Maxi USB HID

## theC64 Joystick — USB HID Output Profile

The official theC64 joystick presents as a USB HID gamepad with the following
controls (as enumerated in its HID descriptor):

| HID Report Field   | theC64 Function        | Notes                                      |
|--------------------|------------------------|--------------------------------------------|
| Axis X / Y         | Joystick directions    | Standard ±127 axes                        |
| Button 1           | **Fire (Left)**        | Primary fire — most games                 |
| Button 2           | **Fire (Right) / Up**  | Used for "jump" in some games             |
| Button 3           | Space                  | Maps to SPACE on keyboard                 |
| Button 4           | Return/Enter           | Maps to RETURN on keyboard                |
| Button 5           | A (Menu select)        | Confirm/select in menus                   |
| Button 6           | Menu (Escape/Back)     | Opens in-game menu or goes back           |
| Button 7           | Restore                | Maps to Restore key (NMI)                 |

> Note: The exact button numbering matches the order reported in the HID
> descriptor. Button 1 is the primary fire; Button 2 doubles as "up" on the
> joystick axis AND a second fire, matching the original C64 hardware which
> had "up as jump" via joystick up.

---

## Sega Genesis 6-Button Controller — Available Inputs

| Genesis Button | Physical Location      | Typical Use                               |
|----------------|------------------------|-------------------------------------------|
| Up             | D-Pad                  | Move up                                   |
| Down           | D-Pad                  | Move down                                 |
| Left           | D-Pad                  | Move left                                 |
| Right          | D-Pad                  | Move right                                |
| A              | Face button (left)     | Action                                    |
| B              | Face button (middle)   | Action                                    |
| C              | Face button (right)    | Action                                    |
| X              | Face button (top-left) | Action                                    |
| Y              | Face button (top-mid)  | Action                                    |
| Z              | Face button (top-right)| Action                                    |
| Start          | Center button          | Start / Pause                             |
| Mode           | Small center button    | Mode toggle                               |

---

## Implemented Mapping

| Genesis Input  | → theC64 HID Output    | Reasoning                                         |
|----------------|------------------------|---------------------------------------------------|
| D-Pad Up       | Axis Y = -127          | Standard joystick up                              |
| D-Pad Down     | Axis Y = +127          | Standard joystick down                            |
| D-Pad Left     | Axis X = -127          | Standard joystick left                            |
| D-Pad Right    | Axis X = +127          | Standard joystick right                           |
| **B**          | **Button 1 (Fire)**    | **Reserved: Primary fire — center-easy button**  |
| **A**          | **Button 2 (Up/Jump)** | **Reserved: Up axis + fire — jump in jump games** |
| C              | Button 3 (Space)       | Space bar / secondary action                      |
| Y              | Button 4 (Return)      | Enter / confirm                                   |
| X              | Button 5 (Menu select) | Menu navigation confirm                           |
| Z              | Button 6 (Menu/Back)   | Menu back / escape                                |
| Start          | Button 7 (Restore)     | Restore / NMI — system menu                       |
| Mode           | (unused / spare)       | Can be used for future mapping                    |

### Why B for Fire and A for Jump?
- On a Genesis pad held naturally, **B** sits under the right thumb as the
  most natural "fire" button — ergonomically equivalent to the original
  Atari-style single fire button.
- **A** is immediately to the left of B and easy to reach with the same thumb,
  making it natural for jump games where rapid fire+jump is needed.
- This preserves the original "up = jump" behaviour expected by C64 software
  while giving a dedicated ergonomic button for it.

---

## A Button — Jump Behaviour (Always Active)

When `A` is pressed:
- Sends **both** Button 2 AND Axis Y = -127 simultaneously so that
  both "joystick up" and the HID button signal are asserted — covering all
  C64 games regardless of whether they use the button or the axis for jumping.

This behaviour is hardcoded in `genesis_to_c64()` in `c64_genesis_adapter.py`
and is always active; there is no runtime toggle.
