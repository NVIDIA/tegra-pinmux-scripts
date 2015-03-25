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

last_reg = soc.soc_drv_reg_base - 4
for group in soc.drive_groups_by_reg():
    if group.reg != last_reg + 4:
        eqs = ' = (0x%x / 4)' % (group.reg - soc.soc_drv_reg_base)
    else:
        eqs = ''
    print('\tPMUX_DRVGRP_%s%s,' % (group.fullname.upper()[6:], eqs), file=f)
    last_reg = group.reg

print('''\
	PMUX_DRVGRP_COUNT,
};
''', file=f, end='')

if len(soc.mipi_pad_ctrl_groups_by_reg()):
    print('''\

enum pmux_mipipadctrlgrp {
''', file=f, end='')

    last_reg = soc.soc_mipipadctrl_reg_base - 4
    for group in soc.mipi_pad_ctrl_groups_by_reg():
        if group.reg != last_reg + 4:
            eqs = ' = (0x%x / 4)' % (group.reg - soc.soc_mipipadctrl_reg_base)
        else:
            eqs = ''
        print('\tPMUX_MIPIPADCTRLGRP_%s%s,' % (group.name.upper(), eqs), file=f)

    print('''\
	PMUX_MIPIPADCTRLGRP_COUNT,
};
''', file=f, end='')

print('''\

enum pmux_func {
	PMUX_FUNC_DEFAULT,
''', file=f, end='')

for func in soc.functions_by_alpha():
    if func.name.startswith('rsvd'):
        continue
    print('\tPMUX_FUNC_%s,' % func.name.upper(), file=f)


print('''\
	PMUX_FUNC_RSVD%d,
	PMUX_FUNC_RSVD%d,
	PMUX_FUNC_RSVD%d,
	PMUX_FUNC_RSVD%d,
	PMUX_FUNC_COUNT,
};

''' % tuple(soc.soc_rsvd_base + i for i in range(4)), file=f, end='')

print('#define TEGRA_PMX_SOC_DRV_GROUP_BASE_REG 0x%x' % soc.soc_drv_reg_base, file=f)
if len(soc.mipi_pad_ctrl_groups_by_reg()):
    print('#define TEGRA_PMX_SOC_MIPIPADCTRL_BASE_REG 0x%x' % soc.soc_mipipadctrl_reg_base, file=f)

if soc.soc_has_io_clamping:
    print('#define TEGRA_PMX_SOC_HAS_IO_CLAMPING', file=f)

print('#define TEGRA_PMX_SOC_HAS_DRVGRPS', file=f)

if len(soc.mipi_pad_ctrl_groups_by_reg()):
    print('#define TEGRA_PMX_SOC_HAS_MIPI_PAD_CTRL_GRPS', file=f)

if soc.soc_drvgroups_have_lpmd:
    print('#define TEGRA_PMX_GRPS_HAVE_LPMD', file=f)

if soc.soc_drvgroups_have_schmitt:
    print('#define TEGRA_PMX_GRPS_HAVE_SCHMT', file=f)

if soc.soc_drvgroups_have_hsm:
    print('#define TEGRA_PMX_GRPS_HAVE_HSM', file=f)

print('#define TEGRA_PMX_PINS_HAVE_E_INPUT', file=f)
print('#define TEGRA_PMX_PINS_HAVE_LOCK', file=f)

if soc.soc_pins_have_od:
    print('#define TEGRA_PMX_PINS_HAVE_OD', file=f)

if soc.soc_pins_have_ior:
    print('#define TEGRA_PMX_PINS_HAVE_IO_RESET', file=f)

if soc.soc_pins_have_rcv_sel:
    print('#define TEGRA_PMX_PINS_HAVE_RCV_SEL', file=f)

if soc.soc_pins_have_e_io_hv:
    print('#define TEGRA_PMX_PINS_HAVE_E_IO_HV', file=f)

print('''\
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

if len(soc.mipi_pad_ctrl_groups_by_reg()):
    print('''\

#define MIPIPADCTRL_GRP(grp, f0, f1)	\\
	{				\\
		.funcs = {		\\
			PMUX_FUNC_##f0,	\\
			PMUX_FUNC_##f1,	\\
		},			\\
	}

#define MIPIPADCTRL_RESERVED {}

static const struct pmux_mipipadctrlgrp_desc %s_mipipadctrl_groups[] = {
''' % soc.name, file=f, end='')

    headings = ('pin', 'f0', 'f1')
    rows = []
    last_reg = 0
    for grp in soc.mipi_pad_ctrl_groups_by_reg():
        if grp.reg != last_reg + 4:
            if last_reg:
                for i in range(((grp.reg - last_reg) // 4) - 1):
                    rows.append('\tMIPIPACTRL_RESERVED,',)
            rows.append('\t/* Offset 0x%x */' % grp.reg,)
        last_reg = grp.reg
        row = (grp.name.upper(),)
        for i in range(2):
            row += (grp.funcs[i].upper(),)
        rows.append(row)
    dump_c_table(headings, 'MIPIPADCTRL_GRP', rows, file=f)

    print('''\
};
const struct pmux_mipipadctrlgrp_desc *tegra_soc_mipipadctrl_groups = %s_mipipadctrl_groups;
''' % soc.name, file=f, end='')

f.close()
