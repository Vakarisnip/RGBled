# code.py — CircuitPython SH1106 128x64, 5x5 custom font (“Hello World” centered)
import time
import board
import busio
import digitalio

# ── DISPLAY TUNABLES ─────────────────────────────────────────────────────
I2C_SCL    = board.GP1
I2C_SDA    = board.GP0
I2C_FREQ   = 100_000          # robust; try 400_000 later if stable
OLED_ADDR  = 0x3C             # often 0x3C (sometimes 0x3D)
COL_OFFSET = 2                # try 2, then 0, then 4 if horizontally shifted
MIRROR_H   = True             # A1 vs A0
MIRROR_V   = True             # C8 vs C0
RESET_PIN  = None             # e.g., board.GP2 if your module exposes RST
# ─────────────────────────────────────────────────────────────────────────

# Your exact 5x5 font (rows top→bottom). '1' = pixel on, '0' = off.
FONT5 = {
    "H": [
        "10001",
        "10001",
        "11111",
        "10001",
        "10001",
    ],
    "E": [
        "11111",
        "10000",
        "11111",
        "10000",
        "11111",
    ],
    "L": [
        "10000",
        "10000",
        "10000",
        "10000",
        "11111",
    ],
    "O": [
        "11111",
        "10001",
        "10001",
        "10001",
        "11111",
    ],
    "W": [
        "10001",
        "10101",
        "10101",
        "10101",
        "11111",
    ],
    "R": [
        "11111",
        "10001",
        "11111",
        "11000",
        "10100",
    ],
    "D": [
        "11100",
        "10010",
        "10001",
        "10010",
        "11100",
    ],
    " ": [
        "00000",
        "00000",
        "00000",
        "00000",
        "00000",
    ],
}

class SH1106:
    def __init__(self, i2c, width=128, height=64, addr=0x3C, col_offset=2,
                 mirror_h=True, mirror_v=True, reset_pin=None):
        self.i2c = i2c
        self.addr = addr
        self.width = width
        self.height = height
        self.pages = height // 8
        self.col_offset = col_offset
        self.buffer = bytearray(self.width * self.pages)

        if reset_pin is not None:
            rst = digitalio.DigitalInOut(reset_pin)
            rst.direction = digitalio.Direction.OUTPUT
            rst.value = True;  time.sleep(0.01)
            rst.value = False; time.sleep(0.01)
            rst.value = True;  time.sleep(0.05)

        while not self.i2c.try_lock():
            pass
        try:
            self._init_display(mirror_h, mirror_v)
        finally:
            self.i2c.unlock()

        self.fill(0)
        self.show()

    def _wcmd(self, *cmd_bytes):
        self.i2c.writeto(self.addr, b"\x00" + bytes(cmd_bytes))

    def _wdata(self, chunk):
        self.i2c.writeto(self.addr, b"\x40" + bytes(chunk))

    def _init_display(self, mirror_h, mirror_v):
        self._wcmd(0xAE)                   # display OFF
        self._wcmd(0xD5, 0x80)             # clock
        self._wcmd(0xA8, self.height - 1)  # multiplex
        self._wcmd(0xD3, 0x00)             # display offset
        self._wcmd(0x40)                   # start line 0
        self._wcmd(0xAD, 0x8B)             # DC-DC on
        self._wcmd(0xA1 if mirror_h else 0xA0)  # seg remap
        self._wcmd(0xC8 if mirror_v else 0xC0)  # COM dir
        self._wcmd(0xDA, 0x12)             # COM pins
        self._wcmd(0x81, 0x7F)             # contrast
        self._wcmd(0xD9, 0xF1)             # pre-charge
        self._wcmd(0xDB, 0x40)             # VCOMH
        self._wcmd(0xA4)                   # resume from RAM
        self._wcmd(0xA6)                   # normal
        self._wcmd(0xAF)                   # display ON
        time.sleep(0.02)

    # 1bpp framebuffer helpers
    def fill(self, color):
        c = 0xFF if color else 0x00
        for i in range(len(self.buffer)):
            self.buffer[i] = c

    def pixel(self, x, y, color=1):
        if not (0 <= x < self.width and 0 <= y < self.height):
            return
        page = y >> 3
        bit  = y & 7
        idx  = page * self.width + x
        if color:
            self.buffer[idx] |= (1 << bit)
        else:
            self.buffer[idx] &= ~(1 << bit)

    def text5(self, s, x, y, color=1, spacing=1):
        """Draw text using the 5x5 FONT5 at (x,y)."""
        cx = x
        for ch in s:
            glyph = FONT5.get(ch, FONT5[" "])
            # draw 5 rows × 5 cols
            for row in range(5):
                row_bits = glyph[row]
                for col in range(5):
                    if row_bits[col] == "1":
                        self.pixel(cx + col, y + row, color)
            cx += 5 + spacing  # advance with spacing

    def show(self):
        while not self.i2c.try_lock():
            pass
        try:
            for page in range(self.pages):
                self._wcmd(0xB0 + page)
                col = self.col_offset
                self._wcmd(0x00 | (col & 0x0F))
                self._wcmd(0x10 | ((col >> 4) & 0x0F))

                start = page * self.width
                end   = start + self.width
                line  = self.buffer[start:end]
                for i in range(0, len(line), 16):
                    self._wdata(line[i:i+16])
        finally:
            self.i2c.unlock()

# set up I2C
i2c = busio.I2C(I2C_SCL, I2C_SDA, frequency=I2C_FREQ)

# wait briefly for bus to come ready
t0 = time.monotonic()
while not i2c.try_lock():
    if time.monotonic() - t0 > 1.0:
        break
i2c.unlock()

disp = SH1106(
    i2c,
    width=128,
    height=64,
    addr=OLED_ADDR,
    col_offset=COL_OFFSET,
    mirror_h=MIRROR_H,
    mirror_v=MIRROR_V,
    reset_pin=RESET_PIN
)

# Center "Hello World" using 5x5 + 1px spacing
text = "HELLO WORLD"
char_w = 5
spacing = 1
text_w = len(text) * (char_w + spacing) - spacing
text_h = 5

x = max(0, (disp.width  - text_w) // 2)
y = max(0, (disp.height - text_h) // 2)

disp.fill(0)
disp.text5(text, x, y, color=1, spacing=spacing)
disp.show()

while True:
    time.sleep(1)

