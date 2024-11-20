# buttons.py
"""
    implement press and hold buttons
    class Button implements a click event
    class HoldButton extends Button to include a hold event
    - button methods are coroutines and include self-polling methods
    class ButtonSet implements a group of buttons returning events via a buffer
"""

import asyncio

from time import ticks_ms, ticks_diff
from machine import Pin, Signal
from micropython import const


class Buffer:
    """
        Single item buffer
        In this context: interface between a button-group and the event consumer
        - put_lock supports multiple data producers
        - interface matches Queue
    """

    def __init__(self):
        self._item = None
        self.is_data = asyncio.Event()
        self.is_space = asyncio.Event()
        self.put_lock = asyncio.Lock()
        self.get_lock = asyncio.Lock()
        self.is_space.set()

    async def put(self, item):
        """ coro: add item to buffer
            - put_lock supports multiple producers
        """
        async with self.put_lock:
            await self.is_space.wait()
            self._item = item
            self.is_data.set()
            self.is_space.clear()

    async def get(self):
        """ coro: remove item from buffer
            - get_lock supports multiple consumers
        """
        async with self.get_lock:
            await self.is_data.wait()
            self.is_data.clear()
            self.is_space.set()
            return self._item

    @property
    def q_len(self):
        """ match queue interface """
        if self.is_data.is_set():
            return 1
        else:
            return 0


class Button:
    """ button with click event"""
    # button states
    WAIT = const('0')
    CLICK = const('1')

    POLL_INTERVAL = const(20)  # ms

    def __init__(self, pin, name=''):
        # Signal wraps pull-up logic with invert
        self.pin = pin
        self._hw_in = Signal(pin, Pin.IN, Pin.PULL_UP, invert=True)
        if name:
            self.name = name
        else:
            self.name = str(pin)
        self.mode = 'click'
        self.active = True
        # self.events = {'wait': self.name + '0', 'click': self.name + '1'}
        self.press_ev = asyncio.Event()  # starts cleared
        self.ev_type = self.WAIT

    async def poll_state(self):
        """ poll self for click event
            - event is set on button release
            - event handler must call clear_event
        """
        prev_pin_state = self._hw_in.value()
        while True:
            pin_state = self._hw_in.value()
            if pin_state != prev_pin_state:
                if not pin_state:
                    self.ev_type = self.CLICK
                    self.press_ev.set()
                prev_pin_state = pin_state
            await asyncio.sleep_ms(self.POLL_INTERVAL)

    def clear_state(self):
        """ set event to 0 """
        self.ev_type = self.WAIT
        self.press_ev.clear()


class HoldButton(Button):
    """ button add hold event """
    HOLD = const('2')
    T_HOLD = const(750)  # ms

    def __init__(self, pin, name=''):
        super().__init__(pin, name)
        self.mode = 'click or hold'

    async def poll_state(self):
        """ poll self for click or hold events
            - button event must be cleared by event handler
            - elapsed time measured in ms
        """
        on_time = None
        prev_pin_state = self._hw_in.value()
        while True:
            pin_state = self._hw_in.value()
            if pin_state != prev_pin_state:
                time_stamp = ticks_ms()
                if pin_state:
                    on_time = time_stamp
                else:
                    if ticks_diff(time_stamp, on_time) < self.T_HOLD:
                        self.ev_type = self.CLICK
                    else:
                        self.ev_type = self.HOLD
                    self.press_ev.set()
                prev_pin_state = pin_state
            await asyncio.sleep_ms(self.POLL_INTERVAL)

    def __str__(self):
        return f'{self.name} {self.ev_type}'

    def __repr__(self):
        return f'{self.name} {self.ev_type}'


class ButtonGroup:
    """
        Instantiates a group of Button and/or HoldButton objects.
        Event parameters are returned through a single-item buffer
        Coro poll-buttons task must be created externally to avoid side effects
        - buffer put() is coordinated with by btn_lock
        - this is acquired and cleared by the calling method(s)
    """

    def __init__(self, button_set):
        self.button_set = button_set
        self.buffer = Buffer()
        self.btn_lock = asyncio.Lock()

    async def process_event(self, btn):
        """ coro: passes a button event to the system """
        while True:
            await btn.press_ev.wait()
            if not self.btn_lock.locked():
                await self.buffer.put((btn.name, btn.ev_type))
            btn.clear_state()

    def poll_buttons(self):
        """ buttons self-poll """
        for b in self.button_set:
            asyncio.create_task(b.poll_state())
            asyncio.create_task(self.process_event(b))

    def list_buttons(self):
        """ print list of buttons """
        print('Buttons:')
        for b in self.button_set:
            print(f'  pin: {b.pin}; name: {b.name}; mode: {b.mode}')


async def main():
    """ coro: test Button and HoldButton classes """

    class TestButtons:

        def __init__(self, btn_group_):
            self.btn_group = btn_group_

        async def process_button_input(self):
            while True:
                await self.btn_group.buffer.is_data.wait()
                async with self.btn_group.btn_lock:  # block button input
                    data = await self.btn_group.buffer.get()
                    print(data)
                    if data == ('D', '2'):
                        break
                    await asyncio.sleep_ms(3000)  # demonstrate blocking period

    buttons = (HoldButton(6, 'A'),
               HoldButton(7, 'B'),
               HoldButton(8, 'C'),
               HoldButton(9, 'D')
               )

    # ButtonGroup creates button-handling tasks; events are put() in buff
    btn_group = ButtonGroup(buttons)
    btn_group.poll_buttons()
    btn_group.list_buttons()

    test_buttons = TestButtons(btn_group)
    print(test_buttons)
    await test_buttons.process_button_input()


if __name__ == '__main__':
    try:
        asyncio.run(main())
    finally:
        asyncio.new_event_loop()  # clear retained event
        print('execution complete')
