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
    def __init__(self, soc, signal, gpio, num, data):
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
        fields = ('reg', 'f0', 'f1', 'f2', 'f3',)
        if soc.soc_pins_all_have_od:
            self.od = True
        elif soc.soc_pins_have_od:
            fields += ('od',)
        if soc.soc_pins_have_ior:
            fields += ('ior',)
        if soc.soc_pins_have_rcv_sel:
            fields += ('rcv_sel', )
        if soc.soc_pins_have_hsm:
            fields += ('hsm', )
        if soc.soc_pins_all_have_schmitt:
            self.schmitt = True
        elif soc.soc_pins_have_schmitt:
            fields += ('schmitt', )
        if soc.soc_pins_have_drvtype:
            fields += ('drvtype', )
        if soc.soc_pins_have_e_io_hv:
            fields += ('e_io_hv', )
        for i, field in enumerate(fields):
            self.__setattr__(field, data[i])
        self.funcs = (self.f0, self.f1, self.f2, self.f3)
        self.per_pin_drive_group = None

    def set_per_pin_drive_group(self, g):
        self.per_pin_drive_group = g

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
    def __init__(self, soc, data):
        num = _gpio_number(data[1])
        PinBase.__init__(self, soc, data[0], data[1], num, data[2:])

class Pin(PinBase):
    def __init__(self, soc, num, data):
        PinBase.__init__(self, soc, data[0], '', num, data[1:])

class DriveGroup(ReprDictObj):
    def __init__(self, soc, data, gpios_pins):
        fields = ('name', 'reg', )
        if soc.soc_drvgroups_have_hsm:
            fields += ('hsm_b',)
        if soc.soc_drvgroups_have_schmitt:
            fields += ('schmitt_b',)
        if soc.soc_drvgroups_have_lpmd:
            fields += ('lpmd_b',)
        fields += ('drvdn_b', 'drvdn_w', 'drvup_b', 'drvup_w', 'slwr_b',
            'slwr_w', 'slwf_b', 'slwf_w')
        if soc.soc_drvgroups_have_drvtype:
            fields += ('drvtype', )
        for i, field in enumerate(fields):
            self.__setattr__(field, data[i])
        self.gpios_pins = gpios_pins
        self.fullname = 'drive_' + self.name
        self.has_matching_pin = (
            soc.soc_combine_pin_drvgroup and
            (len(gpios_pins) == 1) and
            (gpios_pins[0].shortname == self.name)
        )
        if self.has_matching_pin:
            gpios_pins[0].set_per_pin_drive_group(self)


class MipiPadCtrlGroup(ReprDictObj):
    def __init__(self, soc, data, gpios_pins):
        fields = ('name', 'reg', 'bit', 'f0', 'f1')
        for i, field in enumerate(fields):
            self.__setattr__(field, data[i])
        self.gpios_pins = gpios_pins
        self.fullname = 'mipi_pad_ctrl_' + self.name
        self.funcs = (self.f0, self.f1)

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
            ('soc_has_io_clamping', None),
            ('soc_combine_pin_drvgroup', None),
            ('soc_rsvd_base', None),
            ('soc_drvgroups_have_drvtype', None),
            ('soc_drvgroups_have_hsm', None),
            ('soc_drvgroups_have_lpmd', None),
            ('soc_drvgroups_have_schmitt', None),
            ('soc_pins_all_have_od', None),
            ('soc_pins_all_have_parked', None),
            ('soc_pins_all_have_schmitt', None),
            ('soc_pins_have_drvtype', None),
            ('soc_pins_have_e_io_hv', None),
            ('soc_pins_have_hsm', None),
            ('soc_pins_have_ior', None),
            ('soc_pins_have_od', None),
            ('soc_pins_have_rcv_sel', None),
            ('soc_pins_have_schmitt', None),
            ('soc_drv_reg_base', None),
            ('soc_mipipadctrl_reg_base', 0),
            ('soc_einput_b', None),
            ('soc_odrain_b', None),
            ('soc_parked_bank', None),
            ('soc_parked_bit', None),
        )
        TopLevelParsedObj.__init__(self, name, copy_attrs, data)

        gpios_pins_by_fullname = {}
        gpios_pins_by_shortname = {}

        self._gpios = []
        for gpiodata in data['gpios']:
            gpio = Gpio(self, gpiodata)
            gpios_pins_by_fullname[gpio.fullname] = gpio
            gpios_pins_by_shortname[gpio.shortname] = gpio
            self._gpios.append(gpio)

        self._pins = []
        for num, pindata in enumerate(data['pins']):
            pin = Pin(self, num, pindata)
            gpios_pins_by_fullname[pin.fullname] = pin
            gpios_pins_by_shortname[pin.shortname] = pin
            self._pins.append(pin)

        self._drive_groups = []
        for drive_group in data['drive_groups']:
            names = data['drive_group_pins'][drive_group[0]]
            gpios_pins = []
            for name in names:
                gpios_pins.append(gpios_pins_by_fullname[name])
            self._drive_groups.append(DriveGroup(self, drive_group, gpios_pins))

        self._mipi_pad_ctrl_groups = []
        for group in data.get('mipi_pad_ctrl_groups', []):
            names = data['mipi_pad_ctrl_group_pins'][group[0]]
            gpios_pins = []
            for name in names:
                gpios_pins.append(gpios_pins_by_fullname[name])
            self._mipi_pad_ctrl_groups.append(MipiPadCtrlGroup(self, group, gpios_pins))

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

        self._mipi_pad_ctrl_groups_by_reg = sorted(self._mipi_pad_ctrl_groups, key=lambda group: group.reg)
        self._mipi_pad_ctrl_groups_by_alpha = sorted(self._mipi_pad_ctrl_groups, key=lambda group: group.name)

        functions = collections.OrderedDict()
        for pin in self._gpios + self._pins:
            if not pin.reg:
                continue
            for func in pin.funcs:
                if func not in functions:
                    functions[func] = Function(func)
                functions[func]._add_pin(pin)
        for group in self._mipi_pad_ctrl_groups:
            for func in (group.f0, group.f1):
                if func not in functions:
                    functions[func] = Function(func)
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

    def mipi_pad_ctrl_groups_by_conf_order(self):
        return self._mipi_pad_ctrl_groups

    def mipi_pad_ctrl_groups_by_reg(self):
        return self._mipi_pad_ctrl_groups_by_reg

    def mipi_pad_ctrl_groups_by_alpha(self):
        return self._mipi_pad_ctrl_groups_by_alpha

    def mipi_pad_ctrl_group_by_name(self, name):
        for mipi_pad_ctrl in self._mipi_pad_ctrl_groups:
            if name == mipi_pad_ctrl.name:
                return mipi_pad_ctrl
        return None

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
