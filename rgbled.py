# code.py — CircuitPython, SH1106 128x64 on I2C (SCL=GP1, SDA=GP0)
# Draws "Hello World" centered. No external libs needed.

import time
import board
import busio

# ─────────────────────────────────────────────────────────────────────────
# Minimal SH1106 driver (I2C)
# Notes:
#  - Typical SH1106 I2C address is 0x3C
#  - SH1106 has 132 columns internally; many modules need a +2 column offset
# ─────────────────────────────────────────────────────────────────────────
class SH1106:
    def __init__(self, i2c, width=128, height=64, addr=0x3C, col_offset=2):
        self.i2c = i2c
        self.addr = addr
        self.width = width
        self.height = height
        self.pages = height // 8
        self.col_offset = col_offset  # many SH1106 need 2
        self.buffer = bytearray(self.width * self.pages)

        # Wait for I2C ready
        while not self.i2c.try_lock():
            pass
        try:
            self._init_display()
        finally:
            self.i2c.unlock()

    def _cmd(self, *bytes_):
        # control byte 0x00 = command stream
        data = bytes([0x00, *bytes_])
        self.i2c.writeto(self.addr, data)

    def _data(self, chunk):
        # control byte 0x40 = data stream
        # chunk should be <= ~16-32 bytes for safety
        self.i2c.writeto(self.addr, b"\x40" + bytes(chunk))

    def _init_display(self):
        # Init sequence for SH1106 128x64
        self._cmd(0xAE)                      # display OFF
        self._cmd(0xD5, 0x80)                # clock
        self._cmd(0xA8, self.height - 1)     # multiplex
        self._cmd(0xD3, 0x00)                # display offset
        self._cmd(0x40)                      # start line = 0
        self._cmd(0xAD, 0x8B)                # DC-DC on (SH1106 specific on some modules)
        self._cmd(0xA1)                      # segment re-map (mirror horizontally)
        self._cmd(0xC8)                      # COM scan direction (flip vertically)
        self._cmd(0xDA, 0x12)                # COM pins
        self._cmd(0x81, 0x7F)                # contrast
        self._cmd(0xD9, 0xF1)                # pre-charge
        self._cmd(0xDB, 0x40)                # VCOMH
        self._cmd(0xA4)                      # resume display from RAM
        self._cmd(0xA6)                      # normal display (not inverted)
        self._cmd(0xAF)                      # display ON
        self.fill(0)                         # clear
        self.show()

    # Framebuffer helpers (1 bit per pixel, vertical byte pages)
    def fill(self, color):
        c = 0xFF if color else 0x00
        for i in range(len(self.buffer)):
            self.buffer[i] = c

    def pixel(self, x, y, color=1):
        if not (0 <= x < self.width and 0 <= y < self.height):
            return
        page = y // 8
        bit = y & 7
        idx = page * self.width + x
        if color:
            self.buffer[idx] |= (1 << bit)
        else:
            self.buffer[idx] &= ~(1 << bit)

    def blit_glyph(self, x, y, glyph_cols):
        """Draw a 5x7 glyph given as 5 bytes (each byte = column, LSB=top)."""
        for cx, col_byte in enumerate(glyph_cols):
            for bit in range(7):  # 7 pixels tall
                px_on = (col_byte >> bit) & 1
                self.pixel(x + cx, y + bit, px_on)
        # 1px horizontal space after glyph
        # (no need to explicitly clear; just leave as background)

    def text(self, s, x, y, font):
        for ch in s:
            cols = font.get(ch)
            if cols is None:
                cols = font.get("?")
            self.blit_glyph(x, y, cols)
            x += 6  # 5px glyph + 1px space

    def show(self):
        # Write buffer page by page
        while not self.i2c.try_lock():
            pass
        try:
            for page in range(self.pages):
                self._cmd(0xB0 + page)  # set page
                # set column with offset (lower 4 bits, then upper 4 bits)
                col = self.col_offset
                self._cmd(0x00 | (col & 0x0F))        # low nibble
                self._cmd(0x10 | ((col >> 4) & 0x0F)) # high nibble

                # send one page (width bytes)
                start = page * self.width
                end = start + self.width
                line = self.buffer[start:end]

                # Write in chunks (some I2C stacks prefer <= 16-32 bytes)
                chunk_size = 16
                for i in range(0, len(line), chunk_size):
                    self._data(line[i:i+chunk_size])
        finally:
            self.i2c.unlock()


# ─────────────────────────────────────────────────────────────────────────
# Minimal 5x7 font (columns, LSB at top). Only chars used in "Hello World".
# You can extend this dict with more glyphs if needed.
# Each list has 5 bytes = 5 columns.
FONT_5x7 = {
    "H": [0x7F, 0x08, 0x08, 0x08, 0x7F],
    "e": [0x3C, 0x4A, 0x4A, 0x4A, 0x30],
    "l": [0x00, 0x41, 0x7F, 0x40, 0x00],
    "o": [0x38, 0x44, 0x44, 0x44, 0x38],
    " ": [0x00, 0x00, 0x00, 0x00, 0x00],
    "W": [0x7C, 0x02, 0x0C, 0x02, 0x7C],
    "r": [0x7C, 0x08, 0x04, 0x04, 0x08],  # simple 'r'
    "d": [0x38, 0x44, 0x44, 0x24, 0x7C],
    "!": [0x00, 0x00, 0x5F, 0x00, 0x00],
    "?": [0x02, 0x01, 0x59, 0x09, 0x06],
}

# Lowercase 'h' for "Hello" capital H + lowercase ello (we already have 'H', 'e', 'l', 'o').
# 'W' is uppercase in "World". We already have 'r','l','d'.

# ─────────────────────────────────────────────────────────────────────────
# Main: set up I2C on GP1/GP0 and draw centered text
i2c = busio.I2C(board.GP1, board.GP0, frequency=400000)  # SCL=GP1, SDA=GP0

# Some boards need a moment for I2C to lock
t0 = time.monotonic()
while not i2c.try_lock():
    if time.monotonic() - t0 > 1.0:
        break
i2c.unlock()

disp = SH1106(i2c, 128, 64, addr=0x3C, col_offset=2)

# Prepare text and compute centered position
text = "Hello World"
text_px_w = len(text) * 6 - 1  # 5px per char + 1px space; last char no trailing space
text_px_h = 7
x = max(0, (disp.width  - text_px_w) // 2)
y = max(0, (disp.height - text_px_h) // 2)

disp.fill(0)
disp.text(text, x, y, FONT_5x7)
disp.show()

# Keep it displayed
while True:
    time.sleep(1)
