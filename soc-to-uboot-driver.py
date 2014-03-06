#!/usr/bin/env python3

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
import os
import os.path
import sys
import tegra_pmx_soc_parser
from tegra_pmx_utils import *

dbg = False

parser = argparse.ArgumentParser(description='Create a U-Boot pinctrl ' +
    'driver from an SoC config file')
parser.add_argument('--debug', action='store_true', help='Turn on debugging prints')
parser.add_argument('soc', help='SoC to process')
parser.add_argument('header', help='Header file to generate')
parser.add_argument('cfile', help='C file to generate')
args = parser.parse_args()
if args.debug:
    dbg = True
if dbg: print(args)

soc = tegra_pmx_soc_parser.load_soc(args.soc)

f = open(args.header, 'wt')

print('''\
/*
 * Copyright (c) %s, NVIDIA CORPORATION. All rights reserved.
 *
 * SPDX-License-Identifier: GPL-2.0+
 */

#ifndef _%s_PINMUX_H_
#define _%s_PINMUX_H_

enum pmux_pingrp {
''' % (soc.uboot_copyright_years, soc.name.upper(), soc.name.upper()), file=f, end='')

last_reg = 0x3000 - 4
for pin in soc.gpios_pins_by_reg():
    if pin.reg != last_reg + 4:
        eqs = ' = (0x%x / 4)' % (pin.reg - 0x3000)
    else:
        eqs = ''
    print('\tPMUX_PINGRP_%s%s,' % (pin.fullname.upper(), eqs), file=f)
    last_reg = pin.reg

print('''\
	PMUX_PINGRP_COUNT,
};

enum pmux_drvgrp {
''', file=f, end='')

last_reg = 0x868 - 4
for group in soc.drive_groups_by_reg():
    if group.reg != last_reg + 4:
        eqs = ' = (0x%x / 4)' % (group.reg - 0x868)
    else:
        eqs = ''
    print('\tPMUX_DRVGRP_%s%s,' % (group.fullname.upper()[6:], eqs), file=f)
    last_reg = group.reg

print('''\
	PMUX_DRVGRP_COUNT,
};

enum pmux_func {
	PMUX_FUNC_DEFAULT,
''', file=f, end='')

for func in soc.functions_by_alpha():
    if func.name.startswith('rsvd'):
        continue
    print('\tPMUX_FUNC_%s,' % func.name.upper(), file=f)


print('''\
	PMUX_FUNC_RSVD1,
	PMUX_FUNC_RSVD2,
	PMUX_FUNC_RSVD3,
	PMUX_FUNC_RSVD4,
	PMUX_FUNC_COUNT,
};

#define TEGRA_PMX_HAS_PIN_IO_BIT_ETC
''', file=f, end='')

if soc.has_rcv_sel:
    print('#define TEGRA_PMX_HAS_RCV_SEL', file=f)

print('''\
#define TEGRA_PMX_HAS_DRVGRPS
#include <asm/arch-tegra/pinmux.h>

#endif /* _%s_PINMUX_H_ */
''' % soc.name.upper(), file=f, end='')

f.close()
f = open(args.cfile, 'wt')

print('''\
/*
 * Copyright (c) %s, NVIDIA CORPORATION. All rights reserved.
 *
 * SPDX-License-Identifier: GPL-2.0+
 */

#include <common.h>
#include <asm/io.h>
#include <asm/arch/pinmux.h>

#define PIN(pin, f0, f1, f2, f3)	\\
	{				\\
		.funcs = {		\\
			PMUX_FUNC_##f0,	\\
			PMUX_FUNC_##f1,	\\
			PMUX_FUNC_##f2,	\\
			PMUX_FUNC_##f3,	\\
		},			\\
	}

#define PIN_RESERVED {}

static const struct pmux_pingrp_desc %s_pingroups[] = {
''' % (soc.uboot_copyright_years, soc.name), file=f, end='')

headings = ('pin', 'f0', 'f1', 'f2', 'f3')

rows = []
last_reg = 0
for pin in soc.gpios_pins_by_reg():
    if pin.reg != last_reg + 4:
        if last_reg:
            for i in range(((pin.reg - last_reg) // 4) - 1):
                rows.append('\tPIN_RESERVED,',)
        rows.append('\t/* Offset 0x%x */' % pin.reg,)
    last_reg = pin.reg
    row = (pin.fullname.upper(),)
    for i in range(4):
        row += (pin.funcs[i].upper(),)
    rows.append(row)
dump_c_table(headings, 'PIN', rows, file=f)

print('''\
};
const struct pmux_pingrp_desc *tegra_soc_pingroups = %s_pingroups;
''' % soc.name, file=f, end='')

f.close()
