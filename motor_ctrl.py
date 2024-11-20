# motor_ctrl.py

import asyncio

from micropython import const


class Motor:
    """ control mode/direction/speed of a motor
        - negative speeds not initially supported
    """

    ACCEL_STEPS = const(25)

    @staticmethod
    def pc_u16(percentage):
        """ convert positive percentage to 16-bit equivalent """
        if 0 < percentage <= 100:
            return 0xffff * percentage // 100
        else:
            return 0

    def __init__(self, channel, name, min_pc=25):
        self.channel = channel
        self.name = name  # for print or logging
        self.min_u16 = self.pc_u16(min_pc)  # start-up speed
        self.mode = 'S'
        self.speed_u16 = 0
        self.modes = channel.STATES
        self.run_set = {'F', 'R'}

    def set_mode(self, mode):
        """ 'F' forward, 'R' reverse, or 'S' stop  """
        if mode in self.modes:
            self.channel.set_state(mode)
            self.mode = mode
        else:
            print(f'Unknown mode: {mode}')

    def rotate_u16(self, dc_u16):
        """ rotate motor at u16 duty cycle """
        self.channel.set_dc_u16(dc_u16)
        self.speed_u16 = dc_u16

    async def accel_u16(self, target_u16_, period_ms_):
        """ accelerate from rest to target speed in period_ms """
        pause_ms = period_ms_ // self.ACCEL_STEPS
        step_change = (target_u16_ - self.min_u16) // self.ACCEL_STEPS
        speed = self.min_u16
        for _ in range(self.ACCEL_STEPS):
            speed += step_change
            self.rotate_u16(speed)
            await asyncio.sleep_ms(pause_ms)
        self.speed_u16 = target_u16_
        self.rotate_u16(target_u16_)

    async def accel_pc(self, target_pc_, period_ms):
        """ accelerate from current to target speed in trans_period_ms
            - supports (target < current) for deceleration
        """
        if self.mode in self.run_set:
            await self.accel_u16(self.pc_u16(target_pc_), period_ms)
        else:
            self.stop()

    async def decel_u16(self, period_ms_):
        """ accelerate from rest to target speed in period_ms """
        pause_ms = period_ms_ // self.ACCEL_STEPS
        speed = self.speed_u16
        step_change = speed // self.ACCEL_STEPS
        for _ in range(self.ACCEL_STEPS):
            speed -= step_change
            self.rotate_u16(speed)
            await asyncio.sleep_ms(pause_ms)
        self.speed_u16 = 0
        self.rotate_u16(0)

    async def decel_pc(self, period_ms=500):
        """ decelerate from current speed to rest in period_ms """
        if self.mode in self.run_set:
            await self.decel_u16(period_ms)
        else:
            self.stop()

    def halt(self):
        """ set speed immediately to 0 but retain mode """
        self.rotate_u16(0)

    def stop(self):
        """ set mode to 'S'; halt the motor """
        self.set_mode('S')
        self.halt()

    def set_logic_off(self):
        """ turn off channel logic """
        self.channel.set_logic_off()
