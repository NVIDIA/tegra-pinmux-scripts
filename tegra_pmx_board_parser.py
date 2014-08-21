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

import os.path
import sys
import tegra_pmx_soc_parser
from tegra_pmx_parser_utils import *

script_dir = os.path.dirname(os.path.abspath(__file__))
configs_dir = os.path.join(script_dir, 'configs')

class PinConfig(ReprDictObj):
    def __init__(self, soc, data):
        fields = ('fullname', 'mux', 'gpio_init', 'pull', 'tri', 'e_inp', 'od')
        if soc.has_rcv_sel:
            fields += ('rcv_sel', )
        for i, field in enumerate(fields):
            self.__setattr__(field, data[i])
        self.gpio_pin = soc.gpio_or_pin_by_fullname(self.fullname)

class Board(TopLevelParsedObj):
    def __init__(self, name, data):
        TopLevelParsedObj.__init__(self, name, (), data)

        self.varname = name.lower().replace('-', '_')
        self.definename = name.upper().replace('-', '_')

        self.soc = tegra_pmx_soc_parser.load_soc(data['soc'])

        self._pincfgs = []
        for num, pindata in enumerate(data['pins']):
            pincfg = PinConfig(self.soc, pindata)
            self._pincfgs.append(pincfg)

        # FIXME: fill this in...
        self.drvcfg = []

        self._generate_derived_data()

    def _generate_derived_data(self):
        self._pincfgs_by_num = sorted(self._pincfgs, key=lambda pincfg: pincfg.gpio_pin.sort_by_num_key())

    def pincfgs_by_conf_order(self):
        return self._pincfgs

    def pincfgs_by_num(self):
        return self._pincfgs_by_num

    def warn_about_unconfigured_pins(self):
        unconfigured_gpio_pins = {gpio_pin.fullname for gpio_pin in self.soc.gpios_pins_by_num()}
        for gpio_pin in self.pincfgs_by_num():
            unconfigured_gpio_pins.remove(gpio_pin.gpio_pin.fullname)
        for gpio_pin in unconfigured_gpio_pins:
            print('WARNING: Unconfigured pin ' + gpio_pin, file=sys.stderr)

def load_board(boardname):
    fn = os.path.join(configs_dir, boardname + '.board')
    d = {}
    with open(fn) as f:
        code = compile(f.read(), fn, 'exec')
        exec(code, globals(), d)

    return Board(boardname, d)
