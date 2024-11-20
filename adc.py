import asyncio

from machine import Pin, ADC
from micropython import const
from buttons import Button, HoldButton
from lcd_1602 import LcdApi


class Adc:
    """ input from potentiometer to ADC """

    pc_factor = const(655)

    def __init__(self, pin):
        self.adc = ADC(Pin(pin))

    def get_pc(self):
        """ return input setting in range 0 - 99 """
        return self.adc.read_u16() // Adc.pc_factor


async def main():
    async def keep_alive():
        """ coro: to be awaited """
        t = 0
        while t < 600:
            await asyncio.sleep(1)
            t += 1

    async def process_btn_event(btn, btn_lock_):
        """ coro: processes button events """
        track = '1'
        lcd.write_line(0, f'Track: {track}')
        while True:
            await btn.press_ev.wait()
            print(btn.name, btn.ev_type)
            if btn.name == 'A':
                async with btn_lock_:
                    pass
            elif btn.name == 'B':
                async with btn_lock_:
                    if track == '1':
                        track = '2'
                    else:
                        track = '1'
                    lcd.write_line(0, f'Track: {track}')
            elif btn.name == 'C':
                async with btn_lock_:
                    lcd.write_line(0, f'Save? ')
                    lcd.write_line(1, f'Clk:No  Hld:Yes')
                    btn.clear_state()
                    await btn.press_ev.wait()
                    if btn.ev_type == btn.HOLD:
                        # write JSON file
                        lcd.write_line(0, f'Values saved')
                    else:
                        lcd.write_line(0, f'Not saved')
                    await asyncio.sleep_ms(2000)
                    lcd.write_line(0, f'Track: {track}')
                    lcd.write_line(1, '')
            elif btn.name == 'D':
                async with btn_lock_:
                    pass
            btn.clear_state()

    async def process_adc(adc_a, adc_b):
        """ coro: poll the fwd and rev ADC inputs """
        fwd_prev = -1
        rev_prev = -1
        while True:
            fwd_pc = adc_a.get_pc()
            rev_pc = adc_b.get_pc()
            if fwd_pc != fwd_prev or rev_pc != rev_prev:
                lcd.write_line(1, f'F: {fwd_pc:02d}%  R: {rev_pc:02d}%')
                fwd_prev = fwd_pc
                rev_prev = rev_pc
            await asyncio.sleep_ms(200)

    params = {
        'buttons': (Button(6, 'A'), HoldButton(7, 'B'), HoldButton(8, 'C'), HoldButton(9, 'D')),
        'adc': (Adc(26), Adc(27)),
        'i2c_pins': {'sda': 0, 'scl': 1},
        'cols_rows': {'cols': 16, 'rows': 2},
    }

    btn_lock = asyncio.Lock()
    # create tasks to poll buttons and adc
    for b in params['buttons']:
        asyncio.create_task(b.poll_state())  # buttons self-poll
        asyncio.create_task(process_btn_event(b, btn_lock))  # respond to event
    asyncio.create_task(process_adc(*params['adc']))

    lcd = LcdApi(params['i2c_pins'])
    if lcd.lcd_mode:
        lcd.write_line(0, f'ADC Test')
        lcd.write_line(1, f'I2C addr: {lcd.I2C_ADDR}')
    else:
        print('LCD Display not found')

    print(f'System initialised')
    await keep_alive()


if __name__ == '__main__':
    try:
        asyncio.run(main())
    finally:
        asyncio.new_event_loop()  # clear retained ev_type
        print('execution complete')
