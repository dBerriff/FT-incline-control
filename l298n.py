# l298n.py
""" drive a L298N motor controller board
    - developed using MicroPython v1.22.0
    - for Famous Trains Derby by David Jones
    - shared with MERG by David Jones member 9042
"""

from machine import Pin, PWM


class L298nChannel:
    """ L298N H-bridge channel
        - states: 'S': stopped, 'F': forward, 'R': reverse, 'H': halt
        -- 'H' for possible future use
        - frequency and duty cycle: no range checking
        - RP2040 processor: 2 PWM "slice" channels share a common frequency
        -- slices are pins (0 and 1), (2 and 3), ...
    """

    # for (IN1, IN2) or (IN3, IN4)
    # swap 'F' (forward( and 'R' (reverse) values to reverse polarity
    STATES = {
        'S': (1, 1), 'F': (1, 0), 'R': (0, 1), 'H': (0, 0),
        's': (1, 1), 'f': (1, 0), 'r': (0, 1), 'h': (0, 0)
    }

    def __init__(self, pwm_pin, motor_pins_, frequency):
        self.en = PWM(Pin(pwm_pin), freq=frequency, duty_u16=0)
        self.sw_0 = Pin(motor_pins_[0], Pin.OUT)
        self.sw_1 = Pin(motor_pins_[1], Pin.OUT)

    def set_freq(self, frequency):
        """ set pulse frequency """
        self.en.freq(frequency)

    def set_dc_u16(self, dc_u16):
        """ set duty cycle by 16-bit unsigned integer """
        self.en.duty_u16(dc_u16)

    def set_state(self, state):
        """ set H-bridge switch states """
        if state in self.STATES:
            in_0, in_1 = self.STATES[state]
            self.sw_0.value(in_0)
            self.sw_1.value(in_1)

    def set_logic_off(self):
        """ set channel inputs off (0) """
        self.set_dc_u16(0)
        self.sw_0.value(0)
        self.sw_1.value(0)


class L298N:
    """ control a generic L298N H-bridge board
        - 2 channels A and B
        - EN (PWM) labelled: ENA and ENB
        - H-bridge inputs labelled (IN1, IN2), (IN3, IN4)
        - connections: Pico => L298N
        -- pwm_pins => (enA, enB)
        -- sw_pins  => (in1, in2, in3, in4)
    """

    def __init__(self, pwm_pins_, sw_pins_, f_):
        # for debug
        self.pwm_pins = pwm_pins_
        self.sw_pins = sw_pins_
        self.f = f_
        self.channel_a = L298nChannel(
            pwm_pins_['enA'], (sw_pins_['in1'], sw_pins_['in2']), f_)
        self.channel_b = L298nChannel(
            pwm_pins_['enB'], (sw_pins_['in3'], sw_pins_['in4']), f_)

    def set_logic_off(self):
        """ set all control inputs off (0) """
        self.channel_a.set_logic_off()
        self.channel_b.set_logic_off()
