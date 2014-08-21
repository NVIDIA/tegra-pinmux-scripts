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
import datetime
import os.path
import tegra_pmx_board_parser
from tegra_pmx_utils import *

dbg = False

parser = argparse.ArgumentParser(description='Create a U-Boot board pinmux ' +
    'config table from a board config file')
parser.add_argument('--debug', action='store_true', help='Turn on debugging prints')
parser.add_argument('board', help='Board to process')
args = parser.parse_args()
if args.debug:
    dbg = True
if dbg: print(args)

board = tegra_pmx_board_parser.load_board(args.board)

copyright_year = datetime.date.today().year

# FIXME: Need to make rcv_sel parameter to PINCFG() macro below optional
print('''\
/*
 * Copyright (c) %(copyright_year)d, NVIDIA CORPORATION. All rights reserved.
 *
 * SPDX-License-Identifier: GPL-2.0+
 */

#ifndef _PINMUX_CONFIG_%(board_define)s_H_
#define _PINMUX_CONFIG_%(board_define)s_H_

#define GPIO_INIT(_gpio, _init)				\\
	{						\\
		.gpio	= GPIO_P##_gpio,		\\
		.init	= TEGRA_GPIO_INIT_##_init,	\\
	}

static const struct tegra_gpio_config %(board_varname)s_gpio_inits[] = {
''' % {
    'copyright_year': copyright_year,
    'board_define': board.definename,
    'board_varname': board.varname,
}, end='')

gpio_table = []
for pincfg in board.pincfgs_by_num():
    if not pincfg.gpio_init:
        continue
    row = (
        pincfg.gpio_pin.gpio.upper(),
        pincfg.gpio_init.upper(),
    )
    gpio_table.append(row)
headings = ('gpio', 'init_val')
dump_c_table(headings, 'GPIO_INIT', gpio_table)

print('''\
};

#define PINCFG(_pingrp, _mux, _pull, _tri, _io, _od, _rcv_sel)	\\
	{							\\
		.pingrp		= PMUX_PINGRP_##_pingrp,	\\
		.func		= PMUX_FUNC_##_mux,		\\
		.pull		= PMUX_PULL_##_pull,		\\
		.tristate	= PMUX_TRI_##_tri,		\\
		.io		= PMUX_PIN_##_io,		\\
		.od		= PMUX_PIN_OD_##_od,		\\
		.rcv_sel	= PMUX_PIN_RCV_SEL_##_rcv_sel,	\\
		.lock		= PMUX_PIN_LOCK_DEFAULT,	\\
		.ioreset	= PMUX_PIN_IO_RESET_DEFAULT,	\\
	}

static const struct pmux_pingrp_config %(board_varname)s_pingrps[] = {
''' % {
    'board_varname': board.varname,
}, end='')

def mapper_mux(val):
    if val:
        return val.upper()
    else:
        return 'DEFAULT'

def mapper_pull(val):
    if val == 'NONE':
        return 'NORMAL'
    return val

def mapper_tristate(val):
    return {False: 'NORMAL', True: 'TRISTATE'}[val]

def mapper_e_input(val):
    return {False: 'OUTPUT', True: 'INPUT'}[val]

def mapper_od(gpio_pin, val):
    if not gpio_pin.od:
        return 'DEFAULT'
    return {False: 'DISABLE', True: 'ENABLE'}[val]

def mapper_rcv_sel(gpio_pin, val):
    if not gpio_pin.rcv_sel:
        return 'DEFAULT'
    return {False: 'NORMAL', True: 'HIGH'}[val]

pincfg_table = []
for pincfg in board.pincfgs_by_num():
    row = (
        pincfg.fullname.upper(),
        mapper_mux(pincfg.mux),
        mapper_pull(pincfg.pull.upper()),
        mapper_tristate(pincfg.tri),
        mapper_e_input(pincfg.e_inp),
        mapper_od(pincfg.gpio_pin, pincfg.od),
    )
    if board.soc.has_rcv_sel:
        row += (mapper_rcv_sel(pincfg.gpio_pin, pincfg.rcv_sel),)
    pincfg_table.append(row)
headings = ('pingrp', 'mux', 'pull', 'tri', 'e_input', 'od')
if board.soc.has_rcv_sel:
    headings += ('rcv_sel',)
dump_c_table(headings, 'PINCFG', pincfg_table)

print('''\
};

#define DRVCFG(_drvgrp, _slwf, _slwr, _drvup, _drvdn, _lpmd, _schmt, _hsm) \\
	{						\\
		.drvgrp = PMUX_DRVGRP_##_drvgrp,	\\
		.slwf   = _slwf,			\\
		.slwr   = _slwr,			\\
		.drvup  = _drvup,			\\
		.drvdn  = _drvdn,			\\
		.lpmd   = PMUX_LPMD_##_lpmd,		\\
		.schmt  = PMUX_SCHMT_##_schmt,		\\
		.hsm    = PMUX_HSM_##_hsm,		\\
	}

static const struct pmux_drvgrp_config %s_drvgrps[] = {
''' % board.varname, end='')

# FIXME: Handle drive groups

print('''\
};

#endif /* PINMUX_CONFIG_%s_H */
''' % board.definename, end='')

board.warn_about_unconfigured_pins()
