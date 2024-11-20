# incline_state_transition.py

import asyncio
import gc  # garbage collection

from micropython import const
from config import read_cf
from incline_states import Start, Stopped, RunUp, RunDn, CalA, CalB, SaveP, Finish
from buttons import Button, HoldButton, ButtonGroup
from adc import Adc
from lcd_1602 import LcdApi
from l298n import L298N
from motor_ctrl import Motor

"""
    State-transition-model version of control incline
    - 2 x model railway tracks run in synchronisation
    - module incline_states contains a class for each system ev_type
    asyncio-scheduled code
    Structured after tutorial at: https://github.com/peterhinch
"""


class InclineSystem:
    """
        Context for incline system states:
            - start_s (null start ev_type)
            - stopped_s (inactive, waiting for input)
            - run_fwd_s (run incline forward)
            - run_rev_s (run incline in revers)
            - cal_a_s (calibrate A track)
            - cal_b_s (calibrate B track)
            - save_p_s (save or discard calibration settings)
            - finish_s (end execution)
        Each ev_type is instantiated as a class object, each a subclass of State
        Each transition is handled by an ev_type-transition() method
            - each ev_type inherits or overrides these methods/coros:
                - state_enter()
                - schedule_tasks() (default is concurrently)
                  -- task: state_task()
                  -- task: transition_trigger()
                - state_exit()

        Speed-dict structure:
            {'a_speed': {'F': int, 'R': int}, 'b_speed': {'F': int, 'R': int}}

        Button events have value <button_name><event
    """

    VERSION = const('FT Incline v2.0')

    def __init__(self, motor_chan_a_, motor_chan_b_, motor_parameters_,
                 io_p_):
        self.chan_a = motor_chan_a_
        self.chan_b = motor_chan_b_
        self.motor_p = motor_parameters_
        # set up input/output
        lcd = LcdApi(io_p_['i2c_pins'])
        if not lcd.lcd_mode:
            print('LCD Display not found')
        self.lcd = lcd
        self.lcd.clear()
        # 'R' run, 'C' calibrate and 'S' stop buttons required
        self.button_group = ButtonGroup(
            tuple([Button(io_p_['buttons']['R'], 'R'),
                   HoldButton(io_p_['buttons']['C'], 'C'),
                   HoldButton(io_p_['buttons']['S'], 'S')
                   ])
        )
        # forward, reverse ADC
        self.adc_f = Adc(io_p_['adc']['a'])
        self.adc_r = Adc(io_p_['adc']['b'])
        # calibrated-speed dict; outer structure required for inner assignment
        self.cal_speed_dict = {'a_speed': {}, 'b_speed': {}}
        self.load_speed_dict(self.motor_p)
        # no concurrent states or transitions allowed
        # locks enforce the rules. but might not be required if sequence does that
        # btn_lock: required to ignore button events (lock out external demands)
        self.state_lock = asyncio.Lock()
        self.transition_lock = asyncio.Lock()
        self.btn_lock = self.button_group.btn_lock
        self.buffer = self.button_group.buffer  # button event input

        # === system states: instantiate before setting transitions
        self.start_s = Start(self)
        self.stopped_s = Stopped(self)
        self.run_fwd_s = RunUp(self)
        self.run_rev_s = RunDn(self)
        self.cal_a_s = CalA(self)
        self.cal_b_s = CalB(self)
        self.save_p_s = SaveP(self)
        self.finish_s = Finish(self)

        # === system transitions
        self.start_s.transitions = {'auto': self.stopped_s}
        self.stopped_s.transitions = {'R1': self.run_fwd_s,
                                      'C1': self.cal_a_s,
                                      'S2': self.finish_s
                                      }
        self.run_fwd_s.transitions = {'R1': self.run_rev_s,
                                      'S1': self.stopped_s
                                      }
        self.run_rev_s.transitions = {'R1': self.run_fwd_s,
                                      'S1': self.stopped_s
                                      }
        self.cal_a_s.transitions = {'C1': self.cal_b_s,
                                    'S1': self.stopped_s
                                    }
        self.cal_b_s.transitions = {'C1': self.save_p_s,
                                    'S1': self.stopped_s
                                    }
        self.save_p_s.transitions = {'C1': self.stopped_s,
                                     'C2': self.cal_a_s
                                     }
        self.finish_s.transitions = {'auto': None}
        # ===

        # start the system
        self.prev_state_name = ''
        self.state = self.start_s
        self.run = True
        asyncio.create_task(self.state.state_enter())  # cannot await in init
        self.button_group.poll_buttons()  # activate button self-polling
        self.position = 'U'  # guess. 'U': up, 'D': down - required for calibrate
        self.parameter_change = False

    def load_speed_dict(self, source_dict):
        """ assigns parameter values to cal_speed_dict; correct structure assumed """
        for k_1 in ('a_speed', 'b_speed'):
            for k_2 in ('F', 'R'):
                self.cal_speed_dict[k_1][k_2] = source_dict[k_1][k_2]

    async def transition(self, new_state):
        """ transition from current to new ev_type """
        await self.state.state_exit()
        async with self.transition_lock:
            self.prev_state_name = str(self.state.name)
            self.state = new_state
            gc.collect()
            # print(f'Free memory: {gc.mem_free()}')
            asyncio.create_task(self.state.state_enter())

    async def run_system(self):
        """ run the system """
        while self.run:
            await asyncio.sleep_ms(20)

    # motor-control method specific to the incline
    async def run_motors(self, direction_):
        """ run both incline motors """

        async def start_a_b():
            """ accelerate both tracks """
            self.chan_a.set_mode(a_mode)
            self.chan_b.set_mode(b_mode)
            await asyncio.gather(self.chan_a.accel_pc(self.cal_speed_dict['a_speed'][a_mode], 1000),
                                 self.chan_b.accel_pc(self.cal_speed_dict['b_speed'][b_mode], 1000)
                                 )

        async def stop_a_b():
            """ decelerate both tracks """
            await asyncio.gather(self.chan_a.decel_pc(1000),
                                 self.chan_b.decel_pc(1000)
                                 )

        if direction_ == 'D':
            a_mode = 'R'
            b_mode = 'F'
        elif direction_ == 'U':
            a_mode = 'F'
            b_mode = 'R'
        else:
            print(f'Unrecognised direction: {direction_}')
            return
        speed_string = (f'A: {self.cal_speed_dict['a_speed'][a_mode]:02d}  ' +
                        f'B: {self.cal_speed_dict['b_speed'][b_mode]:02d}  ')
        await self.lcd.write_display(f'{a_mode} Accel ', speed_string)
        await start_a_b()
        self.lcd.write_line(0, f'{a_mode} Hold: {self.motor_p['hold_ms']}ms')
        await asyncio.sleep_ms(self.motor_p['hold_ms'])
        await self.lcd.write_display(f'{a_mode} Decel ',
                                     f'A: {0:02d}  B: {0:02d}  ')
        await stop_a_b()
        await self.lcd.write_display(f'{a_mode} Stationary', ' ')
        self.position = direction_


async def main():
    """ load and run ev_type-transition system """
    print('FT Incline v2.0')
    print('Loading system parameters')
    io_p = read_cf('io_p.json')
    l298n_p = read_cf('l298n_p.json')
    motor_p = read_cf('motor_p.json')
    motor_board = L298N({key: int(l298n_p['pins'][key]) for key in ('enA', 'enB')},
                        {key: int(l298n_p['pins'][key]) for key in ('in1', 'in2', 'in3', 'in4')},
                        l298n_p['pulse_f'])
    system = InclineSystem(Motor(motor_board.channel_a, 'A'),
                           Motor(motor_board.channel_b, 'B'),
                           motor_p, io_p)
    print(f'Running the system: {system.VERSION}')
    try:
        await system.run_system()
    finally:
        print('Closing down the system')


if __name__ == '__main__':
    try:
        asyncio.run(main())
    finally:
        asyncio.new_event_loop()  # clear retained ev_type
        print('Execution complete')
