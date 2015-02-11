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

parser = argparse.ArgumentParser(description='Create a kernel pinctrl ' +
    'driver from an SoC config file')
parser.add_argument('--debug', action='store_true', help='Turn on debugging prints')
parser.add_argument('soc', help='SoC to process')
args = parser.parse_args()
if args.debug:
    dbg = True
if dbg: print(args)

soc = tegra_pmx_soc_parser.load_soc(args.soc)

print('''\
/*
 * Pinctrl data for the NVIDIA %s pinmux
 *
 * Copyright (c) %s, NVIDIA CORPORATION.  All rights reserved.
 *
 * This program is free software; you can redistribute it and/or modify it
 * under the terms and conditions of the GNU General Public License,
 * version 2, as published by the Free Software Foundation.
 *
 * This program is distributed in the hope it will be useful, but WITHOUT
 * ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
 * FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License for
 * more details.
 */

#include <linux/module.h>
#include <linux/of.h>
#include <linux/platform_device.h>
#include <linux/pinctrl/pinctrl.h>
#include <linux/pinctrl/pinmux.h>

#include "pinctrl-tegra.h"

/*
 * Most pins affected by the pinmux can also be GPIOs. Define these first.
 * These must match how the GPIO driver names/numbers its pins.
 */
''' % (soc.titlename, soc.kernel_copyright_years), end='')

# Do not add any more exceptions here; new SoCs should be formatted correctly
if soc.name == 'tegra30':
    define_column = 41
else:
    define_column = 49

emit_define('_GPIO(offset)', '(offset)', define_column)
print()

last_gpio_define = None
for gpio in soc.gpios_by_num():
    emit_define(gpio.define, '_GPIO(%d)' % gpio.num, define_column)
    last_gpio_define = gpio.define

print()
print('/* All non-GPIO pins follow */')
emit_define('NUM_GPIOS', '(%s + 1)' % last_gpio_define, define_column)
emit_define('_PIN(offset)', '(NUM_GPIOS + (offset))', define_column)
print()
print('/* Non-GPIO pins */')

for pin in soc.pins_by_num():
    emit_define(pin.define, '_PIN(%d)' % pin.num, define_column)

print()
print('static const struct pinctrl_pin_desc %s_pins[] = {' % soc.name)
for pin in soc.gpios_pins_by_num():
    print('\tPINCTRL_PIN(%s, "%s"),' % (pin.define, pin.desc))
print('};')

for pin in soc.gpios_pins_by_num():
    if not pin.reg:
        continue
    print('''\

static const unsigned %s_pins[] = {
	%s,
};
''' % (pin.fullname, pin.define), end='')

# Do not add any more exceptions here; new SoCs should be formatted correctly
if soc.name == 'tegra30':
    f = soc.drive_groups_by_alpha
else:
    f = soc.drive_groups_by_reg
for group in f():
    if group.has_matching_pin:
        continue
    print('''\

static const unsigned %s_pins[] = {
''' % group.fullname, end='')
    for pin in group.gpios_pins:
        print('\t%s,' % pin.define)
    print('};');

for group in soc.mipi_pad_ctrl_groups_by_reg():
    print('''\

static const unsigned %s_pins[] = {
''' % group.fullname, end='')
    for pin in group.gpios_pins:
        print('\t%s,' % pin.define)
    print('};');

print('''\

enum tegra_mux {
''', end='')

for func in soc.functions_by_alpha():
    print('\tTEGRA_MUX_%s,' % func.name.upper())

print('''\
};

#define FUNCTION(fname)					\\
	{						\\
		.name = #fname,				\\
	}

static struct tegra_function %s_functions[] = {
''' % soc.name, end='')

for func in soc.functions_by_alpha():
    print('\tFUNCTION(%s),' % func.name)

drv_pingroup_val = "0x%x" % soc.soc_drv_reg_base
print('''\
};

#define DRV_PINGROUP_REG_A		%(drv_pingroup_val)s	/* bank 0 */
#define PINGROUP_REG_A			0x3000	/* bank 1 */
''' % globals(), end='')

if len(soc.mipi_pad_ctrl_groups_by_reg()):
    print('#define MIPI_PAD_CTRL_PINGROUP_REG_A	0x820	/* bank 2 */''')

print('''\

#define DRV_PINGROUP_REG(r)		((r) - DRV_PINGROUP_REG_A)
#define PINGROUP_REG(r)			((r) - PINGROUP_REG_A)
''', end='')

if len(soc.mipi_pad_ctrl_groups_by_reg()):
    print('''\
#define MIPI_PAD_CTRL_PINGROUP_REG_Y(r)	((r) - MIPI_PAD_CTRL_PINGROUP_REG_A)
''', end='')

print('''\

#define PINGROUP_BIT_Y(b)		(b)
#define PINGROUP_BIT_N(b)		(-1)

''', end='')

params = ['pg_name', 'f0', 'f1', 'f2', 'f3', 'r']
if soc.soc_pins_have_od and not soc.soc_pins_all_have_od:
    params += ['od',]
if soc.soc_pins_have_ior:
    params += ['ior',]
if soc.soc_pins_have_rcv_sel:
    params += ['rcv_sel',]
if soc.soc_pins_have_hsm:
    params += ['hsm',]
if soc.soc_pins_have_schmitt and not soc.soc_pins_all_have_schmitt:
    params += ['schmitt',]
if soc.soc_pins_have_drvtype:
    params += ['drvtype',]
if soc.soc_pins_have_e_io_hv:
    params += ['e_io_hv',]
drive_params = ['drvdn_b', 'drvdn_w', 'drvup_b', 'drvup_w', 'slwr_b', 'slwr_w', 'slwf_b', 'slwf_w']
if soc.soc_combine_pin_drvgroup:
    params += ['rdrv',]
    params += drive_params

s = gen_wrapped_c_macro_header('PINGROUP', params)

einput_val = str(soc.soc_einput_b)

if soc.soc_pins_have_od:
    if soc.soc_pins_all_have_od:
        odrain_val = str(soc.soc_odrain_b)
    else:
        odrain_val = 'PINGROUP_BIT_##od(%s)' % str(soc.soc_odrain_b)
else:
        odrain_val = '-1'

if soc.soc_pins_have_ior:
    ioreset_val = 'PINGROUP_BIT_##ior(8)'
else:
    ioreset_val = '-1'

# rcv_sel and e_io_hv are different names for essentially the same thing.
# Re-use the field to save space
if soc.soc_pins_have_rcv_sel:
    rcv_sel_val = 'PINGROUP_BIT_##rcv_sel(9),'
elif soc.soc_pins_have_e_io_hv:
    rcv_sel_val = 'PINGROUP_BIT_##e_io_hv(10),'
else:
    rcv_sel_val = '-1,'

s += '''\
	{
		.name = #pg_name,
		.pins = pg_name##_pins,
		.npins = ARRAY_SIZE(pg_name##_pins),
		.funcs = {
			TEGRA_MUX_##f0,
			TEGRA_MUX_##f1,
			TEGRA_MUX_##f2,
			TEGRA_MUX_##f3,
		},
		.mux_reg = PINGROUP_REG(r),
		.mux_bank = 1,
		.mux_bit = 0,
		.pupd_reg = PINGROUP_REG(r),
		.pupd_bank = 1,
		.pupd_bit = 2,
		.tri_reg = PINGROUP_REG(r),
		.tri_bank = 1,
		.tri_bit = 4,
		.einput_bit = %(einput_val)s,
		.odrain_bit = %(odrain_val)s,
		.lock_bit = 7,
		.ioreset_bit = %(ioreset_val)s,
		.rcv_sel_bit = %(rcv_sel_val)s
''' % globals()

if soc.soc_pins_have_hsm:
    s += '''\
		.hsm_bit = PINGROUP_BIT_##hsm(9),
'''

if soc.soc_pins_have_schmitt:
    if soc.soc_pins_all_have_schmitt:
        s += '''\
		.schmitt_bit = 12,
'''
    else:
        s += '''\
		.schmitt_bit = PINGROUP_BIT_##schmitt(12),
'''

if soc.soc_pins_have_drvtype:
    s += '''\
		.drvtype_bit = PINGROUP_BIT_##drvtype(13),
'''

if soc.soc_combine_pin_drvgroup:
    # FIXME: if !soc.soc_pins_have_hsm, then we should include hsm_bit
    # here. Same for schmitt and drvtype. However, no SoCs have that
    # combination at present, so I don't feel like cluttering the code.
    # We should also handle !soc_drvgroups_have_lpmd.
    s += '''\
		.drv_reg = DRV_PINGROUP_REG(rdrv),
		.drv_bank = 0,
		.lpmd_bit = -1,
		.drvdn_bit = drvdn_b,
		.drvdn_width = drvdn_w,
		.drvup_bit = drvup_b,
		.drvup_width = drvup_w,
		.slwr_bit = slwr_b,
		.slwr_width = slwr_w,
		.slwf_bit = slwf_b,
		.slwf_width = slwf_w,
'''
else:
    s += '''\
		.drv_reg = -1,
'''

s = append_aligned_tabs_indent_with_tabs(s)
print(s)

print('''\
	}

''', end='')

params = ['pg_name', 'r']
if soc.soc_drvgroups_have_hsm:
    params += ['hsm_b',]
if soc.soc_drvgroups_have_schmitt:
    params += ['schmitt_b',]
if soc.soc_drvgroups_have_lpmd:
    params += ['lpmd_b',]
params += drive_params
if soc.soc_drvgroups_have_drvtype:
    params += ['drvtype',]

s = gen_wrapped_c_macro_header('DRV_PINGROUP', params)

if soc.soc_drvgroups_have_hsm:
    hsm_bit_val = 'hsm_b'
else:
    hsm_bit_val = '-1'

if soc.soc_drvgroups_have_schmitt:
    schmitt_bit_val = 'schmitt_b'
else:
    schmitt_bit_val = '-1'

if soc.soc_drvgroups_have_lpmd:
    lpmd_bit_val = 'lpmd_b'
else:
    lpmd_bit_val = '-1'

if soc.soc_drvgroups_have_drvtype:
    drvtype_bit_val = 'PINGROUP_BIT_##drvtype(6),'
else:
    drvtype_bit_val = '-1,'

s += '''\
	{
		.name = "drive_" #pg_name,
		.pins = drive_##pg_name##_pins,
		.npins = ARRAY_SIZE(drive_##pg_name##_pins),
		.mux_reg = -1,
		.pupd_reg = -1,
		.tri_reg = -1,
		.einput_bit = -1,
		.odrain_bit = -1,
		.lock_bit = -1,
		.ioreset_bit = -1,
		.rcv_sel_bit = -1,
		.drv_reg = DRV_PINGROUP_REG(r),
		.drv_bank = 0,
		.hsm_bit = %(hsm_bit_val)s,
		.schmitt_bit = %(schmitt_bit_val)s,
		.lpmd_bit = %(lpmd_bit_val)s,
		.drvdn_bit = drvdn_b,
		.drvdn_width = drvdn_w,
		.drvup_bit = drvup_b,
		.drvup_width = drvup_w,
		.slwr_bit = slwr_b,
		.slwr_width = slwr_w,
		.slwf_bit = slwf_b,
		.slwf_width = slwf_w,
		.drvtype_bit = %(drvtype_bit_val)s
''' % globals()

s = append_aligned_tabs_indent_with_tabs(s)
print(s)

print('''\
	}

''', end='')

if len(soc.mipi_pad_ctrl_groups_by_reg()):
    print('''\
#define MIPI_PAD_CTRL_PINGROUP(pg_name, r, b, f0, f1)			\\
	{								\\
		.name = "mipi_pad_ctrl_" #pg_name,			\\
		.pins = mipi_pad_ctrl_##pg_name##_pins,			\\
		.npins = ARRAY_SIZE(mipi_pad_ctrl_##pg_name##_pins),	\\
		.funcs = {						\\
			TEGRA_MUX_ ## f0,				\\
			TEGRA_MUX_ ## f1,				\\
			TEGRA_MUX_RSVD3,				\\
			TEGRA_MUX_RSVD4,				\\
		},							\\
		.mux_reg = MIPI_PAD_CTRL_PINGROUP_REG_Y(r),		\\
		.mux_bank = 2,						\\
		.mux_bit = b,						\\
		.pupd_reg = -1,						\\
		.tri_reg = -1,						\\
		.einput_bit = -1,					\\
		.odrain_bit = -1,					\\
		.lock_bit = -1,						\\
		.ioreset_bit = -1,					\\
		.rcv_sel_bit = -1,					\\
		.drv_reg = -1,						\\
	}

''', end='')

print('''\
static const struct tegra_pingroup %s_groups[] = {
''' % soc.name, end='')

# Do not add any more exceptions here; new SoCs should be formatted correctly
if soc.name == 'tegra30':
    max_gpio_pin_len = max([len(pin.fullname) for pin in soc.gpios_pins_by_reg()])
    max_f0_len = 12
    max_f1_len = 12
    max_f2_len = 12
    max_f3_len = 12
    yn_width = 1
    col_widths = (max_gpio_pin_len, max_f0_len, max_f1_len, max_f2_len, max_f3_len, 6, yn_width, yn_width)
    if soc.soc_pins_have_rcv_sel:
        col_widths += (yn_width,)
    right_justifies = None
elif soc.name in ('tegra114', 'tegra124'):
    max_gpio_pin_len = max([len(pin.fullname) for pin in soc.gpios_pins_by_reg()])
    max_f0_len = 10
    max_f1_len = 10
    max_f2_len = 12
    max_f3_len = 11
    yn_width = 2
    col_widths = (max_gpio_pin_len, max_f0_len, max_f1_len, max_f2_len, max_f3_len, 6, yn_width, yn_width)
    if soc.soc_pins_have_rcv_sel:
        col_widths += (yn_width,)
    right_justifies = (False, False, False, False, False, False, False, True, True, True)
else:
    col_widths = None
    right_justifies = None

headings = ['pg_name', 'f0', 'f1', 'f2', 'f3', 'r']
if soc.soc_pins_have_od and not soc.soc_pins_all_have_od:
    headings += ['od',]
if soc.soc_pins_have_ior:
    headings += ['ior',]
if soc.soc_pins_have_rcv_sel:
    headings += ['rcv_sel',]
if soc.soc_pins_have_hsm:
    headings += ['hsm',]
if soc.soc_pins_have_schmitt and not soc.soc_pins_all_have_schmitt:
    headings += ['schmitt',]
if soc.soc_pins_have_drvtype:
    headings += ['drvtype',]
if soc.soc_pins_have_e_io_hv:
    headings += ['e_io_hv',]
if soc.soc_combine_pin_drvgroup:
    headings += ['rdrv',]
    headings += drive_params

rows = []
# Do not add any more exceptions here; new SoCs should be formatted correctly
if soc.name == 'tegra30':
    f = soc.gpios_pins_by_num
else:
    f = soc.gpios_pins_by_reg
for pin in f():
    if not pin.reg:
        continue
    row = (
        pin.fullname,
        pin.f0.upper(),
        pin.f1.upper(),
        pin.f2.upper(),
        pin.f3.upper(),
        '0x%x' % pin.reg,
    )
    if soc.soc_pins_have_od and not soc.soc_pins_all_have_od:
        row += (boolean_to_yn(pin.od),)
    if soc.soc_pins_have_ior:
        row += (boolean_to_yn(pin.ior),)
    if soc.soc_pins_have_rcv_sel:
        row += (boolean_to_yn(pin.rcv_sel),)
    if soc.soc_pins_have_hsm:
        row += (boolean_to_yn(pin.hsm),)
    if soc.soc_pins_have_schmitt and not soc.soc_pins_all_have_schmitt:
        row += (boolean_to_yn(pin.schmitt),)
    if soc.soc_pins_have_drvtype:
        row += (boolean_to_yn(pin.drvtype),)
    if soc.soc_pins_have_e_io_hv:
        row += (boolean_to_yn(pin.e_io_hv),)
    if soc.soc_combine_pin_drvgroup:
        if pin.per_pin_drive_group:
            row += (
                '0x%x' % pin.per_pin_drive_group.reg,
                repr(pin.per_pin_drive_group.drvdn_b),
                repr(pin.per_pin_drive_group.drvdn_w),
                repr(pin.per_pin_drive_group.drvup_b),
                repr(pin.per_pin_drive_group.drvup_w),
                repr(pin.per_pin_drive_group.slwr_b),
                repr(pin.per_pin_drive_group.slwr_w),
                repr(pin.per_pin_drive_group.slwf_b),
                repr(pin.per_pin_drive_group.slwf_w),
            )
        else:
            row += (
                '-1',
                '-1',
                '-1',
                '-1',
                '-1',
                '-1',
                '-1',
                '-1',
                '-1',
            )
    rows.append(row)
dump_c_table(headings, 'PINGROUP', rows, col_widths=col_widths, right_justifies=right_justifies)

# Do not add any more exceptions here; new SoCs should be formatted correctly
if soc.name != 'tegra30':
    print()

max_drvgrp_len = max([len(drvgroup.name) for drvgroup in soc.drive_groups_by_reg()])

print('\t/* pg_name, r, ', end='')
if soc.soc_drvgroups_have_hsm:
    print('hsm_b, ', end='')
if soc.soc_drvgroups_have_schmitt:
    print('schmitt_b, ', end='')
if soc.soc_drvgroups_have_lpmd:
    print('lpmd_b, ', end='')
print('drvdn_b, drvdn_w, drvup_b, drvup_w, slwr_b, slwr_w, slwf_b, slwf_w', end='')
if soc.soc_drvgroups_have_drvtype:
    print(', drvtype', end='')
print(' */')

rows = []
# Do not add any more exceptions here; new SoCs should be formatted correctly
if soc.name == 'tegra30':
    f = soc.drive_groups_by_alpha
else:
    f = soc.drive_groups_by_reg
# Do not add any more exceptions here; new SoCs should be formatted correctly
if soc.name in ('tegra30', 'tegra114', 'tegra124'):
    col_widths = (0, 0, 2, 2, 2, 3, 2, 3, 2, 3, 2, 3, 2, 2)
    right_justifies = (False, False, True, True, True, True, True, True, True, True, True, True, True, True)
else:
    col_widths = None
    right_justifies = None
for drvgroup in f():
    if drvgroup.has_matching_pin:
        continue
    row = (
        drvgroup.name,
        '0x%x' % drvgroup.reg,
    )
    if soc.soc_drvgroups_have_hsm:
        row += (repr(drvgroup.hsm_b),)
    if soc.soc_drvgroups_have_schmitt:
        row += (repr(drvgroup.schmitt_b),)
    if soc.soc_drvgroups_have_lpmd:
        row += (repr(drvgroup.lpmd_b),)
    row += (
        repr(drvgroup.drvdn_b),
        repr(drvgroup.drvdn_w),
        repr(drvgroup.drvup_b),
        repr(drvgroup.drvup_w),
        repr(drvgroup.slwr_b),
        repr(drvgroup.slwr_w),
        repr(drvgroup.slwf_b),
        repr(drvgroup.slwf_w),
    )
    if soc.soc_drvgroups_have_drvtype:
        row += (boolean_to_yn(drvgroup.drvtype),)
    rows.append(row)
dump_c_table(None, 'DRV_PINGROUP', rows, col_widths=col_widths, right_justifies=right_justifies)

if len(soc.mipi_pad_ctrl_groups_by_reg()):
    print()
    headings = ('pg_name', 'r', 'b', 'f0', 'f1')
    rows = []
    for group in soc.mipi_pad_ctrl_groups_by_reg():
        row = (
            group.name,
            '0x%x' % group.reg,
            repr(group.bit),
            group.f0.upper(),
            group.f1.upper(),
        )
    rows.append(row)
    dump_c_table(headings, 'MIPI_PAD_CTRL_PINGROUP', rows )

socvars = {
    'author': soc.kernel_author,
    'soc': soc.name,
    'usoc': soc.titlename,
    'hsm_in_mux': boolean_to_c_bool(soc.soc_pins_have_hsm),
    'schmitt_in_mux': boolean_to_c_bool(soc.soc_pins_have_schmitt),
    'drvtype_in_mux': boolean_to_c_bool(soc.soc_pins_have_drvtype),
}

print('''\
};

static const struct tegra_pinctrl_soc_data %(soc)s_pinctrl = {
	.ngpios = NUM_GPIOS,
	.pins = %(soc)s_pins,
	.npins = ARRAY_SIZE(%(soc)s_pins),
	.functions = %(soc)s_functions,
	.nfunctions = ARRAY_SIZE(%(soc)s_functions),
	.groups = %(soc)s_groups,
	.ngroups = ARRAY_SIZE(%(soc)s_groups),
	.hsm_in_mux = %(hsm_in_mux)s,
	.schmitt_in_mux = %(schmitt_in_mux)s,
	.drvtype_in_mux = %(drvtype_in_mux)s,
};

static int %(soc)s_pinctrl_probe(struct platform_device *pdev)
{
	return tegra_pinctrl_probe(pdev, &%(soc)s_pinctrl);
}

static const struct of_device_id %(soc)s_pinctrl_of_match[] = {
	{ .compatible = "nvidia,%(soc)s-pinmux", },
	{ },
};
MODULE_DEVICE_TABLE(of, %(soc)s_pinctrl_of_match);

static struct platform_driver %(soc)s_pinctrl_driver = {
	.driver = {
		.name = "%(soc)s-pinctrl",
		.of_match_table = %(soc)s_pinctrl_of_match,
	},
	.probe = %(soc)s_pinctrl_probe,
	.remove = tegra_pinctrl_remove,
};
module_platform_driver(%(soc)s_pinctrl_driver);

MODULE_AUTHOR("%(author)s");
MODULE_DESCRIPTION("NVIDIA %(usoc)s pinctrl driver");
MODULE_LICENSE("GPL v2");
''' % socvars, end='')
