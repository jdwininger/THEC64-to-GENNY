"""
boot.py for CircuitPython
Configures USB HID to expose only a custom joystick device matching
this project's 3-byte report format:
  byte0: X axis (int8)
  byte1: Y axis (int8)
  byte2: buttons bits 0..6
"""

import usb_hid

THEC64_JOYSTICK_REPORT_DESCRIPTOR = bytes([
    0x05, 0x01,  # Usage Page (Generic Desktop)
    0x09, 0x04,  # Usage (Joystick)
    0xA1, 0x01,  # Collection (Application)

    # Axes
    0x09, 0x30,  #   Usage (X)
    0x09, 0x31,  #   Usage (Y)
    0x15, 0x81,  #   Logical Minimum (-127)
    0x25, 0x7F,  #   Logical Maximum (127)
    0x75, 0x08,  #   Report Size (8)
    0x95, 0x02,  #   Report Count (2)
    0x81, 0x02,  #   Input (Data, Var, Abs)

    # 7 Buttons
    0x05, 0x09,  #   Usage Page (Button)
    0x19, 0x01,  #   Usage Minimum (Button 1)
    0x29, 0x07,  #   Usage Maximum (Button 7)
    0x15, 0x00,  #   Logical Minimum (0)
    0x25, 0x01,  #   Logical Maximum (1)
    0x75, 0x01,  #   Report Size (1)
    0x95, 0x07,  #   Report Count (7)
    0x81, 0x02,  #   Input (Data, Var, Abs)

    # 1 pad bit
    0x75, 0x01,  #   Report Size (1)
    0x95, 0x01,  #   Report Count (1)
    0x81, 0x03,  #   Input (Const, Var, Abs)

    0xC0,        # End Collection
])

THEC64_JOYSTICK = usb_hid.Device(
    report_descriptor=THEC64_JOYSTICK_REPORT_DESCRIPTOR,
    usage_page=0x01,
    usage=0x04,
    report_ids=(),
    in_report_lengths=(3,),
    out_report_lengths=(0,),
)

# Must run in boot.py so USB descriptors are active at enumeration time.
try:
    usb_hid.enable((THEC64_JOYSTICK,), boot_device=0)
except TypeError:
    usb_hid.enable((THEC64_JOYSTICK,))
