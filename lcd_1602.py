# lcd1602.py
""" Refactor of Waveshare class for RGB1602 I2C Module """

import asyncio
from time import sleep_ms

from machine import Pin, I2C
from micropython import const


class LcdApi:
    """ drive LCD1602 display """

    # not all constants are used
    I2C_ADDR = const(62)  # I2C Address

    CLR_DISP = const(0x01)
    ENTRY_MODE = const(0x04)
    DISP_CONTROL = const(0x08)
    FN_SET = const(0x20)

    # flags for display entry mode
    ENT_LEFT = const(0x02)
    ENT_SHIFT_DEC = const(0x00)

    # flags for display on/off control
    DISP_ON = const(0x04)
    CURS_OFF = const(0x00)
    BLINK_OFF = const(0x00)

    # flags for function set
    MODE_4BIT = const(0x00)
    LINES_2 = const(0x08)
    LINES_1 = const(0x00)
    DOTS_5x8 = const(0x00)

    def __init__(self, pins_, dim_=(16, 2)):
        i = 0 if pins_['sda'] in (0, 4, 8, 12, 16, 20) else 1
        self.i2c = I2C(i, sda=Pin(pins_['sda']), scl=Pin(pins_['scl']), freq=400_000)
        self.dim = {'cols': dim_[0], 'rows': dim_[1]}
        self._cols = self.dim['cols']
        self._rows = self.dim['rows']
        self._show_fn = self.MODE_4BIT | self.LINES_1 | self.DOTS_5x8
        try:
            # address info only; ADDRESS used in code
            self.addresses = self.i2c.scan()
            if self.I2C_ADDR not in self.addresses:
                self.lcd_mode = False
                print(f'Other I2C address found: {self.addresses}')
            else:
                self.lcd_mode = True
        except IndexError:
            self.lcd_mode = False
            print('I2C address not found: print() mode')
        if self.lcd_mode:
            self._start(self._rows)
        self._n_lines = None
        self._curr_line = None
        self._show_ctrl = None
        self._show_mode = None
        self.write_delay_ms = 200  # delay between line-writes

    def _command(self, cmd):
        """ invoke command """
        self.i2c.writeto_mem(self.I2C_ADDR, 0x80, chr(cmd))

    def _set_cursor(self, col, row):
        """ set cursor for write """
        col |= 0x80 if row == 0 else 0xc0
        self.i2c.writeto(self.I2C_ADDR, bytearray([0x80, col]))

    def _write(self, data):
        """ write out character at cursor position """
        self.i2c.writeto_mem(self.I2C_ADDR, 0x40, chr(data))

    def _write_out(self, arg):
        """ write out bytearray at cursor position """
        for b in bytearray(str(arg), 'utf-8'):
            self.i2c.writeto_mem(self.I2C_ADDR, 0x40, chr(b))

    def _display(self):
        """ set display ev_type (on) """
        self._show_ctrl |= self.DISP_ON
        self._command(self.DISP_CONTROL | self._show_ctrl)

    def _start(self, lines):
        """ start routine as per Waveshare docs """
        self._n_lines = lines
        self._curr_line = 0
        self._show_fn |= self.LINES_2 if lines > 1 else self.LINES_1
        sleep_ms(50)

        # Send function set command 3 times (!)
        for _ in range(3):
            self._command(self.FN_SET | self._show_fn)
            sleep_ms(5)  # wait more than 4.1ms
        # turn the display on, cursor and blinking off
        self._show_ctrl = self.DISP_ON | self.CURS_OFF | self.BLINK_OFF
        self._display()
        self.clear()
        # Initialize to L > R text direction
        self._show_mode = self.ENT_LEFT | self.ENT_SHIFT_DEC
        self._command(self.ENTRY_MODE | self._show_mode)

    # interface functions

    def clear(self):
        if self.lcd_mode:
            self._command(self.CLR_DISP)
            sleep_ms(2)

    def write_line(self, row, text):
        """ write text to left-justified display row """
        if self.lcd_mode:
            self._set_cursor(0, row)
            self._write_out(f'{text:<16}')
        else:
            print(f'{text:<16}')

    async def write_display(self, line_0_str, line_1_str):
        """ write both display lines """
        self.write_line(0, line_0_str)
        await asyncio.sleep_ms(self.write_delay_ms)
        self.write_line(1, line_1_str)

    def write_char(self, col, row, char):
        """ write character to (col, row) """
        if self.lcd_mode:
            self._set_cursor(col, row)
            self._write_out(char)
        else:
            print(f'({col}, {row}): {char}')


class RgbLcd1602(LcdApi):
    """ has errors """
    RGB_ADDR = const(96)  # I2C Address
    # color define
    REG_RED = const(0x04)
    REG_GRN = const(0x03)
    REG_BLU = const(0x02)
    REG_MODE_1 = const(0x00)
    REG_MODE_2 = const(0x01)
    REG_OUTPUT = const(0x08)

    def __init__(self, pins_, dim_=(16, 2)):
        # super() starts LDC display if present
        super().__init__(pins_, dim_)
        self.is_rgb = self.RGB_ADDR in self.addresses
        # start RGB backlight if present
        if self.is_rgb:
            self.rgb_start()

    def set_reg(self, reg, data):
        self.i2c.writeto_mem(self.RGB_ADDR, reg, chr(data))

    def rgb_start(self):
        # backlight init
        self.set_reg(self.REG_MODE_1, 0)
        # set LEDs controllable by both PWM and GRPPWM registers
        self.set_reg(self.REG_OUTPUT, 0xFF)
        # set MODE2 values
        # 0010 0000 -> 0x20  (DMBLNK to 1, ie blinky mode)
        self.set_reg(self.REG_MODE_2, 0x20)
        self.set_colour((127, 127, 127))

    # interface functions

    def set_colour(self, colour):
        """ set text/backlight colour """
        if self.is_rgb:
            self.set_reg(self.REG_RED, colour[0])
            self.set_reg(self.REG_GRN, colour[1])
            self.set_reg(self.REG_BLU, colour[2])
            sleep_ms(2)

    def set_colour_off(self):
        """ turn backlight off """
        if self.is_rgb:
            self.set_colour((0, 0, 0))


def main():
    """ test of LCD """
    pins = {'sda': 0, 'scl': 1}
    lcd = LcdApi(pins)
    print(f'I2C addresses found: {lcd.addresses}')
    lcd.clear()
    sleep_ms(1000)

    if lcd.lcd_mode:
        lcd.write_line(0, f'Test successful')
        sleep_ms(200)
        lcd.write_line(1, f'sda: {pins['sda']} scl: {pins['scl']}')
    else:
        print('LCD Display not found')
        print(pins)


if __name__ == '__main__':
    try:
        main()
    finally:
        print('Execution complete')
