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

import sys

def gen_tab_padding_to(curpos, targetpos):
    curpos -= 1
    targetpos -= 1
    if (targetpos & 7):
        raise Exception(str(targetpos) + ' is not a TAB stop')
    left = targetpos - curpos
    tabs = (left + 7) // 8
    return '\t' * tabs

def emit_tab_padding_to(curpos, targetpos):
    print(gen_tab_padding_to(curpos, targetpos), end='')

def emit_padded_field(s, maxl, skip_comma=False, right_justify=False, file=sys.stdout):
    pad = (' ' * (maxl - len(s)))
    if right_justify:
        print(pad, file=file, end='')
    print(s, file=file, end='')
    if skip_comma:
        return
    print(', ', file=file, end='')
    if not right_justify:
        print(pad, file=file, end='')

def emit_define(define, value, valuecol):
    s = '#define ' + define
    print(s, end='')
    emit_tab_padding_to(len(s) + 1, valuecol)
    print(value)

def gen_wrapped_c_macro_header(macro, params):
    intro = '#define %s(' % macro
    intro_space = ' ' * len(intro)
    s = ''
    l = intro
    for i, param in enumerate(params):
        if i != 0:
            prefix = ' '
        else:
            prefix = ''
        if i == len(params) - 1:
            suffix = ')'
        else:
            suffix = ','
        #           ', '             ','
        if (len(l) + len(prefix) + len(param) + len(suffix)) < 71:
            l += prefix + param + suffix
        else:
            s += l + '\n'
            l = intro_space + param + suffix
    if l:
        s += l
        s += '\n'
    return s

def len_evaluating_tabs(s):
    l = 0
    for c in s:
        if c == '\t':
            l = (l + 8) & ~7
        else:
            l += 1
    return l

def append_aligned_tabs_indent_with_tabs(s, min_slashpos):
    lines = s.split('\n')
    if lines[-1].strip() == '':
        del lines[-1]
    # This is intended to translate leading spaces to TABs, so that callers
    # don't have to work out the right number of TABs to use. It also would
    # affect intra-line space, but there is none in practice so far.
    for i, l in enumerate(lines):
        lines[i] = l.replace('        ', '\t')
    max_len = 0
    for l in lines:
        max_len = max(max_len, len_evaluating_tabs(l))
    max_len = max(max_len, min_slashpos)
    tabpos = (max_len + 7) & ~7
    for i, l in enumerate(lines):
        lines[i] += gen_tab_padding_to(len_evaluating_tabs(l) + 1, tabpos + 1) + '\\'
    return '\n'.join(lines)

def yn_to_boolean(s):
    return {'N': False, 'Y': True}[s]

def boolean_to_yn(val):
    return {True: 'Y', False: 'N'}[val]

def boolean_to_c_bool(val):
    return {True: 'true', False: 'false'}[val]

def dump_table(heading_prefix, heading_suffix, headings, row_prefix, row_suffix, rows, col_widths, file, right_justifies):
    num_cols = 0
    if headings:
        num_cols = max(num_cols, len(headings))
    if col_widths:
        num_cols = max(num_cols, len(col_widths))
    for row in rows:
        if type(row) == str:
            continue
        num_cols = max(num_cols, len(row))
    widths = [0] * num_cols

    if col_widths:
        for col, val in enumerate(col_widths):
            if not val:
                continue
            widths[col] = val

    if headings:
        for col, val in enumerate(headings):
            if col_widths and col_widths[col]:
                continue
            widths[col] = len(val)

    for row in rows:
        if type(row) == str:
            continue
        for col, val in enumerate(row):
            if col_widths and col_widths[col]:
                continue
            widths[col] = max(widths[col], len(val))

    if headings:
        print(heading_prefix, end='', file=file)
        for col, heading in enumerate(headings):
            emit_padded_field(heading, widths[col], skip_comma = (col == len(headings) - 1), file=file)
        print(heading_suffix, file=file)

    for row in rows:
        if type(row) == str:
            print(row, file=file)
        else:
            print(row_prefix, end='', file=file)
            force_comma = len(row) == 1
            for col, val in enumerate(row):
                if right_justifies:
                    right_justify = right_justifies[col]
                else:
                    right_justify = False
                emit_padded_field(val, widths[col], skip_comma = (col == len(row) - 1) and not force_comma, file=file, right_justify=right_justify)
            print(row_suffix, file=file)

def dump_py_table(headings, rows, col_widths=None, file=sys.stdout, right_justifies=None):
    dump_table('    #', '', headings, '    (', '),', rows, col_widths, file, right_justifies)

def dump_c_table(headings, macro_name, rows, col_widths=None, file=sys.stdout, right_justifies=None, row_indent='\t'):
    dump_table(row_indent + '/* ' + ' ' * (len(macro_name) - 2), ' */', headings, row_indent + macro_name + '(', '),', rows, col_widths, file, right_justifies)

def spreadsheet_col_name_to_num(col):
    if len(col) == 2:
        return ((ord(col[0]) - ord('A') + 1) * 26) + (ord(col[1]) - ord('A'))
    elif len(col) == 1:
        return ord(col[0]) - ord('A')
    else:
        raise Exception('Bad column name ' + col)

def rsvd_0base_to_1base(f):
    if not f.startswith('rsvd'):
        return f
    n = int(f[4:])
    n += 1
    return 'rsvd' + str(n)
