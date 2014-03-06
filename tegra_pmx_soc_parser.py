# Copyright (c) 2014, NVIDIA CORPORATION. All rights reserved.
#
# Permission is hereby granted, free of charge, to any person obtaining a
# copy of this software and associated documentation files (the "Software"),
# to deal in the Software without restriction, including without limitation
# the rights to use, copy, modify, merge, publish, distribute, sublicense,
# and/or sell copies of the Software, and to permit persons to whom the
# Software is furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.  IN NO EVENT SHALL
# THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
# DEALINGS IN THE SOFTWARE.

import collections
import os.path
from tegra_pmx_parser_utils import *

script_dir = os.path.dirname(os.path.abspath(__file__))
configs_dir = os.path.join(script_dir, 'configs')

class PinBase(ReprDictObj):
    def __init__(self, has_rcv_sel, signal, gpio, num, data):
        self.signal = signal
        self.gpio = gpio
        self.num = num
        fields = []
        if self.signal:
            fields += (self.signal,)
        if self.gpio:
            fields += ('p' + self.gpio,)
        self.fullname = '_'.join((fields))
        if self.signal:
            self.shortname = self.signal
        else:
            self.shortname = self.gpio
        self.define = 'TEGRA_PIN_' + '_'.join(fields).upper()
        self.desc = ' '.join(fields).upper()
        if not data:
            self.reg = None
            return
        fields = ('reg', 'f0', 'f1', 'f2', 'f3', 'od', 'ior')
        if has_rcv_sel:
            fields += ('rcv_sel', )
        for i, field in enumerate(fields):
            self.__setattr__(field, data[i])
        self.funcs = (self.f0, self.f1, self.f2, self.f3)

    def sort_by_num_key(self):
        return (self.__class__ == Pin, self.num)

def _gpio_number(gpion):
    if len(gpion) == 2:
        bank = ord(gpion[0]) - ord('a')
        index = ord(gpion[1]) - ord('0')
    else:
        bank = ord(gpion[0]) - ord('a') + 26
        index = ord(gpion[2]) - ord('0')
    return (bank * 8) + index

class Gpio(PinBase):
    def __init__(self, data, has_rcv_sel):
        num = _gpio_number(data[1])
        PinBase.__init__(self, has_rcv_sel, data[0], data[1], num, data[2:])

class Pin(PinBase):
    def __init__(self, num, data, has_rcv_sel):
        PinBase.__init__(self, has_rcv_sel, data[0], '', num, data[1:])

class DriveGroup(ReprDictObj):
    def __init__(self, data, gpios_pins, has_drvtype):
        fields = ('name', 'reg', 'hsm_b', 'schmitt_b', 'lpmd_b', 'drvdn_b',
                'drvdn_w', 'drvup_b', 'drvup_w', 'slwr_b', 'slwr_w', 'slwf_b',
                'slwf_w')
        if has_drvtype:
            fields += ('drvtype', )
        for i, field in enumerate(fields):
            self.__setattr__(field, data[i])
        self.gpios_pins = gpios_pins
        self.fullname = 'drive_' + self.name

class Function(ReprDictObj):
    def __init__(self, name):
        self.name = name
        self.pins = []

    def _add_pin(self, pin):
        self.pins.append(pin)

class Soc(TopLevelParsedObj):
    def __init__(self, name, data):
        copy_attrs = (
            ('kernel_copyright_years', 2014),
            ('kernel_author', 'NVIDIA'),
            ('uboot_copyright_years', 2014),
            ('has_rcv_sel', True),
            ('has_drvtype', True),
        )
        TopLevelParsedObj.__init__(self, name, copy_attrs, data)

        gpios_pins_by_name = {}

        self._gpios = []
        for gpiodata in data['gpios']:
            gpio = Gpio(gpiodata, self.has_rcv_sel)
            gpios_pins_by_name[gpio.fullname] = gpio
            self._gpios.append(gpio)

        self._pins = []
        for num, pindata in enumerate(data['pins']):
            pin = Pin(num, pindata, self.has_rcv_sel)
            gpios_pins_by_name[pin.fullname] = pin
            self._pins.append(pin)

        self._drive_groups = []
        for drive_group in data['drive_groups']:
            names = data['drive_group_pins'][drive_group[0]]
            gpios_pins = []
            for name in names:
                gpios_pins.append(gpios_pins_by_name[name])
            self._drive_groups.append(DriveGroup(drive_group, gpios_pins, self.has_drvtype))

        self._generate_derived_data()

    def _generate_derived_data(self):
        self._gpios_by_num = sorted(self._gpios, key=lambda gpio: gpio.num)
        self._pins_by_num = sorted(self._pins, key=lambda pin: pin.num)
        self._gpios_pins_by_num = sorted(self._gpios + self._pins, key=lambda gpio_pin: gpio_pin.sort_by_num_key())

        gpios_with_reg = [gpio for gpio in self._gpios if gpio.reg]
        pins_with_reg = [pin for pin in self._pins if pin.reg]

        self._gpios_by_reg = sorted(gpios_with_reg, key=lambda gpio: gpio.reg)
        self._pins_by_reg = sorted(pins_with_reg, key=lambda pin: pin.reg)
        self._gpios_pins_by_reg = sorted(gpios_with_reg + pins_with_reg, key=lambda gpio_pin: gpio_pin.reg)

        self._drive_groups_by_reg = sorted(self._drive_groups, key=lambda drive_group: drive_group.reg)
        self._drive_groups_by_alpha = sorted(self._drive_groups, key=lambda drive_group: drive_group.name)

        functions = collections.OrderedDict()
        for pin in self._gpios + self._pins:
            if not pin.reg:
                continue
            for func in pin.funcs:
                if func not in functions:
                    functions[func] = Function(func)
                functions[func]._add_pin(pin)
        self._functions = functions.values()
        self._functions_by_alpha = sorted(self._functions, key=lambda f: f.name)

    def gpios_by_conf_order(self):
        return self._gpios

    def gpios_by_num(self):
        return self._gpios_by_num

    def gpios_by_reg(self):
        return self._gpios_by_reg

    def pins_by_conf_order(self):
        return self._pins

    def pins_by_num(self):
        return self._pins_by_num

    def pins_by_reg(self):
        return self._pins_by_reg

    def gpios_pins_by_num(self):
        return self._gpios_pins_by_num

    def gpios_pins_by_reg(self):
        return self._gpios_pins_by_reg

    def gpio_or_pin_by_name(self, name):
        for gpio_pin in self._gpios_pins_by_num:
            if name == gpio_pin.signal:
                return gpio_pin
            if name == 'gpio_p' + gpio_pin.gpio:
                return gpio_pin
        return None

    def gpio_or_pin_by_fullname(self, name):
        for gpio_pin in self._gpios_pins_by_num:
            if name == gpio_pin.fullname:
                return gpio_pin
        return None

    def drive_groups_by_conf_order(self):
        return self._drive_groups

    def drive_groups_by_reg(self):
        return self._drive_groups_by_reg

    def drive_groups_by_alpha(self):
        return self._drive_groups_by_alpha

    def functions(self):
        return self._functions

    def functions_by_alpha(self):
        return self._functions_by_alpha

def load_soc(socname):
    fn = os.path.join(configs_dir, socname + '.soc')
    d = {}
    with open(fn) as f:
        code = compile(f.read(), fn, 'exec')
        exec(code, globals(), d)

    return Soc(socname, d)
