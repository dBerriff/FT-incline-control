# incline_states.py

""" ev_type classes for system states """

import asyncio

from config import write_cf
from incline_state import InclineState


class Start(InclineState):
    """
        null ev_type to get started
        - immediately transitions to Stopped
    """

    def __init__(self, system):
        super().__init__(system)
        self.name = 'Start'

    async def state_enter(self):
        """ auto trigger to next ev_type """
        print(f'Enter state: {self.name}')
        asyncio.create_task(self.system.transition(self.transitions['auto']))


class Stopped(InclineState):
    """ ev_type: incline stopped """

    def __init__(self, system):
        super().__init__(system)
        self.name = 'Stopped'

    async def state_task(self):
        """ run while in ev_type """
        async with self.system.state_lock:
            await asyncio.sleep_ms(20)


class RunUp(InclineState):
    """ ev_type: run up (A track) under push-button control """

    def __init__(self, system):
        super().__init__(system)
        self.name = 'Run Fwd'

    async def schedule_tasks(self):
        """ create ev_type tasks sequentially """
        await self.state_task()
        await self.transition_trigger()

    async def state_task(self):
        """ run while in ev_type """
        async with self.btn_lock:
            async with self.system.state_lock:
                await self.system.run_motors('U')
                self.system.position = 'U'


class RunDn(InclineState):
    """ ev_type: run down (A track) under push-button control """

    def __init__(self, system):
        super().__init__(system)
        self.name = 'Run Rev'

    async def schedule_tasks(self):
        """ create ev_type tasks sequentially """
        await self.state_task()
        await self.transition_trigger()

    async def state_task(self):
        """ run while in ev_type """
        async with self.btn_lock:
            async with self.system.state_lock:
                await self.system.run_motors('D')
                self.system.position = 'D'


class CalA(InclineState):
    """ ev_type: calibrate PWM for track A motor control """

    def __init__(self, system):
        super().__init__(system)
        self.track = 'A'
        self.name = 'Cal ' + self.track
        self.fwd_demand_pc = 0
        self.rev_demand_pc = 0
        self.speeds = self.system.cal_speed_dict['a_speed']
        self.run_motors = self.system.run_motors

    async def display_parameters(self):
        """ display current speeds and demand speeds """
        await self.system.lcd.write_display(
            f'{self.track} F: {self.speeds['F']:02d}  R: {self.speeds['R']:02d}',
            f'ADC  {self.fwd_demand_pc:02d}     {self.rev_demand_pc:02d}  ')

    async def state_enter(self):
        """ on ev_type entry """
        print(f'Enter state: {self.name}')
        self.remain = True  # flag for while loops
        await self.schedule_tasks()

    async def state_task(self):
        """ run while in ev_type """
        self.fwd_demand_pc = self.adc_f.get_pc()
        self.rev_demand_pc = self.adc_r.get_pc()
        await self.display_parameters()
        while self.remain:
            self.fwd_demand_pc = self.adc_f.get_pc()
            self.rev_demand_pc = self.adc_r.get_pc()
            if self.fwd_demand_pc != self.speeds['F'] or self.rev_demand_pc != self.speeds['R']:
                self.system.parameter_change = True
                self.lcd.write_line(1, f'ADC  {self.fwd_demand_pc:02d}     {self.rev_demand_pc:02d}  ')
                self.speeds['F'] = self.fwd_demand_pc
                self.speeds['R'] = self.rev_demand_pc
            await asyncio.sleep_ms(200)
        self.lcd.write_line(1, f'{""}')
        await asyncio.sleep_ms(200)

    async def transition_trigger(self):
        """ wait for buffer event """

        async def test_run(direction_):
            """ test run the track motors """
            await self.run_motors(direction_)
            self.system.position = direction_
            await self.display_parameters()

        async with self.system.transition_lock:
            while True:
                await self.buffer.is_data.wait()
                # block button inputs until response complete
                async with self.btn_lock:
                    ev_tuple = await self.buffer.get()
                    ev = ev_tuple[0] + ev_tuple[1]
                    print(ev)
                    # 'R1' is a special case
                    if ev == 'R1':
                        if self.system.position == 'D':
                            direction = 'U'
                            print('Run incline Up')
                            await test_run(direction)
                        else:
                            direction = 'D'
                            print('Run incline Down')
                            await test_run(direction)
                    elif ev == 'S1':
                        # restore file speed parameters ready for Stop
                        print('System speeds restored from file parameters')
                        self.system.load_speed_dict(self.system.motor_p)

                    if ev in self.transitions:
                        self.remain = False
                        asyncio.create_task(self.system.transition(self.transitions[ev]))
                        break
                    elif ev != 'R1':
                        print(f'Event {ev} ignored')


class CalB(InclineState):
    """ ev_type: calibrate PWM for track B motor control """

    def __init__(self, system):
        super().__init__(system)
        self.track = 'B'
        self.name = 'Cal ' + self.track
        self.fwd_demand_pc = 0
        self.rev_demand_pc = 0
        self.speeds = self.system.cal_speed_dict['b_speed']
        self.run_motors = self.system.run_motors

    async def display_parameters(self):
        """ display current speeds and demand speeds """
        await self.system.lcd.write_display(
            f'{self.track} F: {self.speeds['F']:02d}  R: {self.speeds['R']:02d}',
            f'ADC  {self.fwd_demand_pc:02d}     {self.rev_demand_pc:02d}  ')

    async def state_enter(self):
        """ on ev_type entry """
        print(f'Enter state: {self.name}')
        self.remain = True  # flag for while loops
        await self.schedule_tasks()

    async def state_task(self):
        """ run while in ev_type """
        self.fwd_demand_pc = self.adc_f.get_pc()
        self.rev_demand_pc = self.adc_r.get_pc()
        await self.display_parameters()
        while self.remain:
            self.fwd_demand_pc = self.adc_f.get_pc()
            self.rev_demand_pc = self.adc_r.get_pc()
            if self.fwd_demand_pc != self.speeds['F'] or self.rev_demand_pc != self.speeds['R']:
                self.system.parameter_change = True
                self.lcd.write_line(1, f'ADC  {self.fwd_demand_pc:02d}     {self.rev_demand_pc:02d}  ')
                self.speeds['F'] = self.fwd_demand_pc
                self.speeds['R'] = self.rev_demand_pc
            await asyncio.sleep_ms(200)
        self.lcd.write_line(1, f'{""}')
        await asyncio.sleep_ms(200)

    async def transition_trigger(self):
        """ wait for buffer event """

        async def test_run(direction_):
            """ test run the track motors """
            await self.run_motors(direction_)
            self.system.position = direction_
            await self.display_parameters()

        async with self.system.transition_lock:
            while True:
                await self.buffer.is_data.wait()
                # block button inputs until response complete
                async with self.btn_lock:
                    ev_tuple = await self.buffer.get()
                    ev = ev_tuple[0] + ev_tuple[1]
                    print(ev)
                    # 'R1' is a special case
                    if ev == 'R1':
                        if self.system.position == 'D':
                            direction = 'U'
                            print('Run incline Up')
                            await test_run(direction)
                        else:
                            direction = 'D'
                            print('Run incline Down')
                            await test_run(direction)
                    elif ev == 'S1':
                        # restore file speed parameters ready for Stop
                        print('System speeds restored from file parameters')
                        self.system.load_speed_dict(self.system.motor_p)

                    if ev in self.transitions:
                        self.remain = False
                        asyncio.create_task(self.system.transition(self.transitions[ev]))
                        break
                    elif ev != 'R1':
                        print(f'Event {ev} ignored')


class SaveP(InclineState):
    """ optionally save motor parameters """

    def __init__(self, system):
        super().__init__(system)
        self.name = 'Save P'

    async def state_enter(self):
        """ on ev_type entry """
        print(f'Enter state: {self.name}')
        self.remain = True  # in ev_type: flag for while loops
        await self.schedule_tasks()

    async def state_task(self):
        """ option to save calibrated speeds
            - write parameters handled as special case in transition_trigger()
        """
        await self.lcd.write_display(f'Save cal?', f'Clk: Y  Hld: N')

    async def transition_trigger(self):
        """ wait for buffer event """
        async with self.system.transition_lock:
            while True:
                await self.buffer.is_data.wait()
                # block further button inputs until response complete
                async with self.btn_lock:
                    ev_tuple = await self.buffer.get()
                    ev = ev_tuple[0] + ev_tuple[1]
                    print(ev)
                    # special case of ev handling
                    if ev == 'C1':
                        if self.system.parameter_change:
                            print('Saving updated speed values')
                            self.system.motor_p.update(self.system.cal_speed_dict)
                            write_cf('motor_p.json', self.system.motor_p)
                            self.system.parameter_change = False
                    elif ev == 'C2':
                        print('Updated speed values discarded and not saved')
                        self.system.load_speed_dict(self.system.motor_p)
                        self.system.parameter_change = False

                    if ev in self.transitions:
                        self.remain = False
                        asyncio.create_task(self.system.transition(self.transitions[ev]))
                        break
                    else:
                        print(f'Event {ev} ignored')


class Finish(InclineState):
    """ finish execution """

    def __init__(self, system):
        super().__init__(system)
        self.name = 'Finish'

    async def schedule_tasks(self):
        """ no ev_type tasks """
        self.system.run = False
        await asyncio.sleep_ms(200)  # for close-down?
