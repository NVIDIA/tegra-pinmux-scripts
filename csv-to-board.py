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

# This parses a CSV version of Logan_customer_pinmux_release.xlsm

import argparse
import csv
import os
import os.path
import sys
import tegra_pmx_soc_parser
from tegra_pmx_utils import *

dbg = False

parser = argparse.ArgumentParser(description='Create a board config' +
    'from a CSV version of the Venice2 pinmux spreadsheet')
parser.add_argument('--debug', action='store_true', help='Turn on debugging prints')
parser.add_argument('--csv', default=argparse.SUPPRESS, help='CSV file to parse')
parser.add_argument('--csv-rsvd-0based', action='store_true', dest='csv_rsvd_0based', default=argparse.SUPPRESS, help='Assume 0-based RSVD numbering')
parser.add_argument('--csv-rsvd-1based', action='store_false', dest='csv_rsvd_0based', default=argparse.SUPPRESS, help='Assume 1-based RSVD numbering')
parser.add_argument('board', help='Board name')
args = parser.parse_args()
if args.debug:
    dbg = True
if dbg: print(args)

supported_boards = {
    'jetson-tk1': {
        # Jetson_TK1_customer_pinmux.xlsm worksheet Jetson TK1 Configuration (1-based rsvd) from:
        # https://developer.nvidia.com/hardware-design-and-development
        'filename': 'csv/jetson-tk1.csv',
        'rsvd_base': 1,
        'soc': 'tegra124',
    },
    'norrin': {
        # PM370_T124_customer_pinmux_1.1.xlsm worksheet Customer_Configuration (0-based rsvd)
        'filename': 'nv-internal-data/PM370_T124_customer_pinmux_1.1.csv',
        'rsvd_base': 0,
        'soc': 'tegra124',
    },
    'venice2': {
        # Venice2_T124_customer_pinmux_based_on_P4_rev47_2013-07-12.xlsm worksheet Customer_Configuration (0-based rsvd)
        'filename': 'nv-internal-data/Venice2_T124_customer_pinmux_based_on_P4_rev47_2013-07-12.csv',
        'rsvd_base': 0,
        'soc': 'tegra124',
    },
}

if not args.board in supported_boards:
    print('ERROR: Unsupported board %s' % args.board, file=sys.stderr)
    sys.exit(1)
board_conf = supported_boards[args.board]
if 'csv' in args:
    board_conf['filename'] = args.csv
if 'csv_rsvd_0based' in args:
    board_conf['rsvd_base'] = {True: 0, False: 1}[args.csv_rsvd_0based]
if dbg: print(board_conf)

soc = tegra_pmx_soc_parser.load_soc(board_conf['soc'])

COL_BALL_NAME = 0
COL_BALL_MID = 1
COL_BALL_DSC = 2
COL_GPIO = 3
COL_F0 = 4
COL_F1 = 5
COL_F2 = 6
COL_F3 = 7
COL_FS = 8
COL_MUX = 9
COL_PUPD = 10
COL_TRI = 11
COL_E_INPUT = 12
COL_GPIO_INIT_VAL = 13
COL_DIRECTION = 14
COL_RCV_SEL = 15

col_names = {
    COL_BALL_NAME:     'Ball Name',
    COL_BALL_MID:      'MID',
    COL_BALL_DSC:      'DSC',
    COL_GPIO:          'GPIO',
    COL_F0:            'F0',
    COL_F1:            'F1',
    COL_F2:            'F2',
    COL_F3:            'F3',
    COL_FS:            'FS',
    COL_MUX:           'Pin Group',
    COL_PUPD:          'PUPD',
    COL_TRI:           'Tristate',
    COL_E_INPUT:       'E_Input',
    COL_GPIO_INIT_VAL: 'GPIO Init Value',
    COL_DIRECTION:     'Pin Direction',
}

if soc.soc_pins_have_rcv_sel:
    col_names[COL_RCV_SEL] = 'High or Normal VIL/VIH'

if soc.soc_pins_have_e_io_hv:
    col_names[COL_RCV_SEL] = '3.3V Tolerance Enable'

cols = {}

def func_munge(f):
    if board_conf['soc'] == 'tegra124':
        if f in ('sdmmc2a', 'sdmmc2b'):
            return 'sdmmc2'
        if f in ('ir3_rxd', 'ir3_txd'):
            return 'irda'
    if soc.soc_rsvd_base != board_conf['rsvd_base']:
        if soc.soc_rsvd_base:
            return rsvd_0base_to_1base(f)
        else:
            raise Exception('CSV 1-based to SoC 0-based not supported')
    return f

def pupd_munge(d):
    return {
        'NORMAL': 'none',
        'PULL_UP': 'up',
        'PULL_DOWN': 'down',
    }[d]

def tri_munge(d):
    return {
        'NORMAL': False,
        'TRISTATE': True,
    }[d]

def e_input_munge(d):
    return {
        'DISABLE': False,
        'ENABLE': True,
    }[d]

def gpio_init_val_munge(d):
    return {
        '0': 'out0',
        '1': 'out1',
    }[d]

def od_from_direction(d):
    return d == 'Open-Drain'

def rcv_sel_munge(d):
    return {
        '': False,
        'NORMAL': False,
        'HIGH': True,
        'Disable': False,
        'Enable': True,
    }[d]

found_header = False
pin_table = []
with open(board_conf['filename'], newline='') as fh:
    csv = csv.reader(fh)
    lnum = 0
    for row in csv:
        lnum += 1

        # Header rows
        if not found_header:
            if row[0] != 'Ball Name':
                if lnum > 25:
                    print('ERROR: Header row not found', file=sys.stderr)
                    sys.exit(1)
                continue
            for colid, coltext in col_names.items():
                try:
                    cols[colid] = row.index(coltext)
                except:
                    if board_conf['soc'] != 'tegra124':
                        raise
                    if colid != COL_RCV_SEL:
                        print('ERROR: Header column "%s" not found' % coltext, file=sys.stderr)
                        sys.exit(1)
                    cols[colid] = None
            found_header = True
            continue

        ball_name = row[cols[COL_BALL_NAME]].lower()
        ball_mid = row[cols[COL_BALL_MID]]
        ball_dsc = row[cols[COL_BALL_DSC]]

        # Section title row
        if not ball_mid and not ball_dsc:
            continue

        mux = func_munge(row[cols[COL_MUX]].lower())

        # Pin not affected by pinmux
        if mux in ('', '0', '#n/a'):
            continue

        if dbg: print(ball_name)

        gpio = row[cols[COL_GPIO]].lower()
        f0 = func_munge(row[cols[COL_F0]].lower())
        f1 = func_munge(row[cols[COL_F1]].lower())
        f2 = func_munge(row[cols[COL_F2]].lower())
        f3 = func_munge(row[cols[COL_F3]].lower())
        fs = func_munge(row[cols[COL_FS]].lower())
        pupd = pupd_munge(row[cols[COL_PUPD]])
        tri = tri_munge(row[cols[COL_TRI]])
        e_input = e_input_munge(row[cols[COL_E_INPUT]])
        od = od_from_direction(row[cols[COL_DIRECTION]])
        if cols[COL_RCV_SEL]:
            rcv_sel = rcv_sel_munge(row[cols[COL_RCV_SEL]])
        else:
            rcv_sel = False

        mux_gpio = mux.startswith('gpio_p') or (mux == gpio)
        if mux_gpio:
            mux = None
            if e_input:
                gpio_init = 'in'
            else:
                gpio_init = gpio_init_val_munge(row[cols[COL_GPIO_INIT_VAL]])
        else:
            gpio_init = None

        gpio_pin = soc.gpio_or_pin_by_name(ball_name)
        for i, func in enumerate((f0, f1, f2, f3)):
            if func != gpio_pin.funcs[i]:
                print('WARNING: %s: F%d mismatch CSV %s vs SOC %s' % (ball_name, i, repr(func), repr(gpio_pin.funcs[i])), file=sys.stderr)
        for i, func in enumerate((f0, f1, f2, f3)):
            if func not in gpio_pin.funcs:
                print('ERROR: %s: F%d CSV %s not in SOC list %s' % (ball_name, i, repr(func), repr(gpio_pin.funcs)), file=sys.stderr)
                sys.exit(1)
        if fs not in (f0, f1, f2, f3):
            print('ERROR: %s: FSAFE CSV %s not in CSV F0..3 %s' % (ball_name, fs, repr((f0, f1, f2, f3))), file=sys.stderr)
            sys.exit(1)
        if mux and mux not in (f0, f1, f2, f3):
            print('ERROR: %s: MUX CSV %s not in CSV F0..3 %s' % (ball_name, mux, repr((f0, f1, f2, f3))), file=sys.stderr)
            sys.exit(1)
        if mux and mux not in gpio_pin.funcs:
            print('ERROR: %s: MUX CSV %s not in SOC F0..3 %s' % (ball_name, mux, repr(gpio_pin.funcs)), file=sys.stderr)
            sys.exit(1)

        if (board_conf['soc'] == 'tegra124') and (ball_name in ('reset_out_n', 'owr', 'hdmi_int', 'ddc_scl', 'ddc_sda')):
            # These balls' pad type is always OD, so we don't need to set it
            # FIXME: The SoC data structure should tell us the pad type instead of hard-coding it
            od = False

        if od and not gpio_pin.od:
            print('WARNING: %s: OD in board file, but pin has no OD' % ball_name, file=sys.stderr)
            od = False
        pin_has_rcv_sel = False
        if soc.soc_pins_have_rcv_sel:
            pin_has_rcv_sel = gpio_pin.rcv_sel
        if soc.soc_pins_have_e_io_hv:
            pin_has_rcv_sel = gpio_pin.e_io_hv
        if rcv_sel and not pin_has_rcv_sel:
            print('WARNING: %s: RCV_SEL/E_IO_HV in board file, but pin does not support it' % ball_name, file=sys.stderr)
            rcv_sel = False

        pin_table.append((repr(gpio_pin.fullname), repr(mux), repr(gpio_init), repr(pupd), repr(tri), repr(e_input), repr(od), repr(rcv_sel)))

headings = ('pin', 'mux', 'gpio_init', 'pull', 'tri', 'e_inp', 'od')
if soc.soc_pins_have_e_io_hv:
    headings += ('e_io_hv',)
if soc.soc_pins_have_rcv_sel:
    headings += ('rcv_sel',)

cfgfile = os.path.join('configs', args.board + '.board')
with open(cfgfile, 'wt') as fh:
    print('soc = \'%s\'' % board_conf['soc'], file=fh)
    print(file=fh)
    print('pins = (', file=fh)

    dump_py_table(headings, pin_table, file=fh)

    print(')', file=fh)
    print('', file=fh)
    print('drive_groups = (', file=fh)
    print(')', file=fh)
