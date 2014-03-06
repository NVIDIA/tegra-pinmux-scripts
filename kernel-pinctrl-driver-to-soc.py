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
import collections
import re
import sys
from tegra_pmx_utils import *

dbg = False

re_siggpio = re.compile('^(.*)_p([a-z]+[0-7])$')

re_copyright = re.compile(' \* Copyright \(c\) (.*), NVIDIA CORPORATION.  All rights reserved.')
re_pin_gpio = re.compile('#define TEGRA_PIN_([A-Z0-9_]+)\s*_GPIO\((\d+)\)')
re_pin_pin = re.compile('#define TEGRA_PIN_([A-Z0-9_]+)\s*_PIN\((\d+)\)')
re_module_author = re.compile('MODULE_AUTHOR\("(.*)"\);')

re_close_brace = re.compile('};')

re_pins_array_start = re.compile('static const struct pinctrl_pin_desc tegra\d+_pins\[\] = \{')
re_pins_array_entry = re.compile('\s+PINCTRL_PIN\(TEGRA_PIN_([A-Z0-9_]+), "([A-Z0-9_ ]+)"\),')

re_group_pins_array_start = re.compile('static const unsigned ([a-z0-9_]+)_pins\[\] = \{')
re_group_pins_array_entry = re.compile('\s+TEGRA_PIN_([A-Z0-9_]+),')

re_mux_array_start = re.compile('enum tegra_mux {')
re_mux_array_entry = re.compile('\s+TEGRA_MUX_([A-Z0-9_]+),')

re_groups_array_start = re.compile('static const struct tegra_pingroup (tegra\d+)_groups\[\] = \{')
re_groups_array_group_entry = re.compile('\s*PINGROUP\((.*)\),')
re_groups_array_drvgroup_entry = re.compile('\s*DRV_PINGROUP\((.*)\),')

num_pin_gpios = 0
pins = collections.OrderedDict()
groups = collections.OrderedDict()
functions = []
soc = None
module_author = None
copyright_years = None
soc_has_rcv_sel = False
soc_has_drvtype = False

state = None
re_state_end = None
state_group = None

def set_state(s, e):
    if dbg: print("SET STATE: " + repr(s))
    global state
    state = s
    global re_state_end
    re_state_end = e

def state_pins_array(l):
    m = re_pins_array_entry.match(l)
    if not m:
        raise Exception('pins array entry cannot be parsed')
    if dbg: print('pin desc:', repr(m.group(1)), repr(m.group(2)))
    pin = m.group(1).lower()
    signal = pins[pin]['signal']
    if pins[pin]['is_gpio']:
        gpio = pins[pin]['gpio']
    else:
        gpio = ''
    pindesc = signal
    if signal and gpio:
        pindesc += ' '
    if gpio:
        pindesc += 'p'
    pindesc += gpio
    if m.group(2) != pindesc.upper():
        raise Exception('pin ' + pin + ' pindesc mismatch')

def state_group_pins_array(l):
    m = re_group_pins_array_entry.match(l)
    if not m:
        raise Exception('group pins array entry cannot be parsed')
    if dbg: print('pin entry:', repr(m.group(1)))
    groups[state_group]['pins'].append(m.group(1).lower())

def state_mux_array(l):
    m = re_mux_array_entry.match(l)
    if not m:
        raise Exception('mux array entry cannot be parsed')
    if dbg: print('function:', repr(m.group(1)))
    functions.append(m.group(1).lower())

def state_groups_array(l):
    m = re_groups_array_group_entry.match(l)
    if m:
        args = re.split('\s*,\s*', m.group(1))
        (group, f0, f1, f2, f3, reg, od, ior) = args[0:8]
        group = group.lower()
        f0 = f0.lower()
        f1 = f1.lower()
        f2 = f2.lower()
        f3 = f3.lower()
        if not group in groups:
            raise Exception('invalid group', group)
        for f in (f0, f1, f2, f3):
            if not f.lower() in functions:
                raise Exception('invalid function', f)
        reg = int(reg, 0)
        od = yn_to_boolean(od)
        ior = yn_to_boolean(ior)
        entry = {
            'is_drive': False,
            'funcs': (f0, f1, f2, f3),
            'reg': reg,
            'od': od,
            'ior': ior,
        }
        if len(args) > 8:
            global soc_has_rcv_sel
            soc_has_rcv_sel = True
            rcv_sel = yn_to_boolean(args[8])
            entry['rcv_sel'] = rcv_sel
        if dbg: print('group entry:', repr(entry))
        groups[group].update(entry)
        return
    m = re_groups_array_drvgroup_entry.match(l)
    if m:
        args = re.split('\s*,\s*', m.group(1))
        (group, reg, hsm_b, schmitt_b, lpmd_b, drvdn_b, drvdn_w, drvup_b, drvup_w, slwr_b, slwr_w, slwf_b, slwf_w) = args[0:13]
        group = 'drive_' + group
        if not group in groups:
            raise Exception('invalid group', group)
        reg = int(reg, 0)
        hsm_b = int(hsm_b, 0)
        schmitt_b = int(schmitt_b, 0)
        lpmd_b = int(lpmd_b, 0)
        drvdn_b = int(drvdn_b, 0)
        drvdn_w = int(drvdn_w, 0)
        drvup_b = int(drvup_b, 0)
        drvup_w = int(drvup_w, 0)
        slwr_b = int(slwr_b, 0)
        slwr_w = int(slwr_w, 0)
        slwf_b = int(slwf_b, 0)
        slwf_w = int(slwf_w, 0)
        entry = {
            'is_drive': True,
            'reg': reg,
            'hsm_b': hsm_b,
            'schmitt_b': schmitt_b,
            'lpmd_b': lpmd_b,
            'drvdn_b': drvdn_b,
            'drvdn_w': drvdn_w,
            'drvup_b': drvup_b,
            'drvup_w': drvup_w,
            'slwr_b': slwr_b,
            'slwr_w': slwr_w,
            'slwf_b': slwf_b,
            'slwf_w': slwf_w,
        }
        if len(args) > 13:
            global soc_has_drvtype
            soc_has_drvtype = True
            drvtype = yn_to_boolean(args[13])
            entry['drvtype'] = drvtype
        if dbg: print('group entry:', repr(entry))
        groups[group].update(entry)
        return
    raise Exception('groups array entry cannot be parsed')

def state_global(l):
    global num_pin_gpios
    global state_group
    global soc
    global copyright_years
    global module_author

    m = re_pins_array_start.match(l)
    if m:
        set_state(state_pins_array, re_close_brace)
        return

    m = re_group_pins_array_start.match(l)
    if m:
        state_group = m.group(1)
        if dbg: print('group pins array:', repr(state_group))
        groups[state_group] = {'pins': []}
        set_state(state_group_pins_array, re_close_brace)
        return

    m = re_mux_array_start.match(l)
    if m:
        set_state(state_mux_array, re_close_brace)
        return

    m = re_groups_array_start.match(l)
    if m:
        soc = m.group(1)
        if dbg: print('groups array (soc %s):'% soc)
        set_state(state_groups_array, re_close_brace)
        return

    m = re_copyright.match(l)
    if m:
        copyright_years = m.group(1)
        return

    m = re_pin_gpio.match(l)
    if m:
        group = m.group(1).lower()
        gpioid = m.group(2)
        m = re_siggpio.match(group)
        if m:
            signal = m.group(1)
            gpio = m.group(2)
        else:
            signal = ''
            gpio = group[1:]

        entry = {
            'is_gpio': True,
            'signal': signal,
            'gpio': gpio,
            'id': int(gpioid),
        }
        if dbg: print('gpio:', repr(group), repr(entry))
        pins[group] = entry
        num_pin_gpios += 1
        return

    m = re_pin_pin.match(l)
    if m:
        entry = {
            'is_gpio': False,
            'signal': m.group(1).lower(),
            'id': int(m.group(2)),
        }
        if dbg: print('pin:', repr(m.group(1)), repr(entry))
        pins[m.group(1).lower()] = entry
        return

    m = re_module_author.match(l)
    if m:
        module_author = m.group(1)
        return

def set_global_state():
    set_state(state_global, None)
    global state_group
    up = None

def main():
    parser = argparse.ArgumentParser(description='Create a pinmux .soc file ' +
        'from kernel pinctrl source code')
    parser.add_argument('--debug', action='store_true',
        help='Turn on debugging prints')
    args = parser.parse_args()
    if args.debug:
        global dbg
        dbg = True
    if dbg: print(args)

    set_global_state()
    for l in sys.stdin.readlines():
        if dbg: print('<<<', repr(l))
        l = re.sub('/\*.*?\*/', '', l)
        if not l.strip():
            continue
        if re_state_end and re_state_end.match(l):
            set_global_state()
            continue
        state(l)

    if dbg:
        print('pins:')
        print(repr(pins))
        print()
        print('groups:')
        print(repr(groups))
        print()
        print('functions:')
        print(repr(functions))

    for group in groups:
        if not 'is_drive' in groups[group]:
            raise Exception('group ' + group + ' not parsed in group array')
        if groups[group]['is_drive']:
            continue
        if len(groups[group]['pins']) != 1:
            raise Exception('group ' + group + ' has more than 1 pin')
        if groups[group]['pins'][0] != group:
            raise Exception('group ' + group + ' pin list does not match')

    for pin in pins:
        if pin not in groups:
            groups[pin] = {'is_drive': False}
            continue
        for (i, function) in enumerate(groups[pin]['funcs']):
            if function.startswith('RSVD') and function != 'RSVD' + str(i + 1):
                raise Exception('pin ' + pin + ' RSVD func ' + i + ' mismatch')

    print('kernel_copyright_years =', repr(copyright_years))
    print('kernel_author =', repr(module_author))
    if not soc_has_rcv_sel:
        print('has_rcv_sel =', repr(soc_has_rcv_sel))
    if not soc_has_drvtype:
        print('has_drvtype =', repr(soc_has_drvtype))
    print()

    def dump_pins(dump_gpios):
        headings = ('name',)
        if dump_gpios:
            headings += ('gpio',)
        headings += ('reg', 'f0', 'f1', 'f2', 'f3', 'od', 'ior')
        if soc_has_rcv_sel:
            headings += ('rcv_sel',)

        rows = []
        for pin in pins:
            p = pins[pin]
            if p['is_gpio'] != dump_gpios:
                continue

            if pin not in groups:
                continue
            g = groups[pin]
            if g['is_drive']:
                continue

            if dump_gpios:
                signal = p['signal']
                gpio = p['gpio']
            else:
                signal = pin
                gpio = None

            row = (repr(signal),)
            if dump_gpios:
                row += (repr(gpio),)
            if 'reg' in g:
                row += ('0x%x' % g['reg'],)
                for func in g['funcs']:
                    row += (repr(func),)
                row += (repr(g['od']), repr(g['ior']))
                if soc_has_rcv_sel:
                    row += (repr(g['rcv_sel']),)

            rows.append(row)

        dump_py_table(headings, rows)

    print('gpios = (')
    dump_pins(True)
    print(')')
    print()
    print('pins = (')
    dump_pins(False)
    print(')')
    print()
    print('drive_groups = (')
    print('    #name, r, hsm_b, schmitt_b, lpmd_b, drvdn_b, drvdn_w, drvup_b, drvup_w, slwr_b, slwr_w, slwf_b, slwf_w', end='')
    if soc_has_drvtype:
        print(', drvtype', end='')
    print()
    rows = []
    for group in groups:
        g = groups[group]
        if not groups[group]['is_drive']:
            continue
        row = (
            repr(group[6:]),
            '0x%x' % g['reg'],
            repr(g['hsm_b']),
            repr(g['schmitt_b']),
            repr(g['lpmd_b']),
            repr(g['drvdn_b']),
            repr(g['drvdn_w']),
            repr(g['drvup_b']),
            repr(g['drvup_w']),
            repr(g['slwr_b']),
            repr(g['slwr_w']),
            repr(g['slwf_b']),
            repr(g['slwf_w']),
        )
        if soc_has_drvtype:
            row += (repr(g['drvtype']),)
        rows.append(row)
    dump_py_table(None, rows)
    print(')')
    print()
    print('drive_group_pins = {')
    for group in groups:
        g = groups[group]
        if not groups[group]['is_drive']:
            continue
        print('    \'%s\': (' % group[6:])
        for pin in g['pins']:
            print('        \'%s\',' % pin)
        print('    ),')
    print('}')

main()
