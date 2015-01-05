#!/usr/bin/python3

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

import argparse
import os.path
import tegra_pmx_board_parser
from tegra_pmx_utils import *

dbg = False

parser = argparse.ArgumentParser(description='Create a kernel device tree ' +
    'pinmux fragment from a board config file')
parser.add_argument('--debug', action='store_true', help='Turn on debugging prints')
parser.add_argument('board', help='Board to process')
args = parser.parse_args()
if args.debug:
    dbg = True
if dbg: print(args)

board = tegra_pmx_board_parser.load_board(args.board)

def mapper_pull(val):
    return 'TEGRA_PIN_PULL_' + val.upper()

def mapper_bool(val):
    return 'TEGRA_PIN_' + {False: 'DISABLE', True: 'ENABLE'}[val]

print('		state_default: pinmux {')

for pincfg in board.pincfgs_by_num():
    print('			' + pincfg.fullname + ' {')
    print('				nvidia,pins = "' + pincfg.fullname + '";')
    if pincfg.mux:
        print('				nvidia,function = "' + pincfg.mux + '";')
    print('				nvidia,pull = <' + mapper_pull(pincfg.pull) + '>;')
    print('				nvidia,tristate = <' + mapper_bool(pincfg.tri) + '>;')
    print('				nvidia,enable-input = <' + mapper_bool(pincfg.e_inp) + '>;')
    if pincfg.gpio_pin.od:
        print('				nvidia,open-drain = <' + mapper_bool(pincfg.od) + '>;')
    if hasattr(pincfg.gpio_pin, 'rcv_sel') and pincfg.gpio_pin.rcv_sel:
        print('				nvidia,rcv-sel = <' + mapper_bool(pincfg.rcv_sel) + '>;')
    print('			};')

# FIXME: Handle drive groups

print('		};')

board.warn_about_unconfigured_pins()
