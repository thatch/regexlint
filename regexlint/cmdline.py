#!/usr/bin/env python2
#
# Copyright 2011-2014 Google Inc.
# Copyright 2018 Tim Hatch
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
from __future__ import print_function

import sys
sys.maxunicode = 65535 # HACK: make Pygments think we're on a narrow build.

import re
import logging
import itertools
import multiprocessing
from six import StringIO

from pygments.lexer import RegexLexer, bygroups
from pygments.token import Token
try:
    from pygments.util import Future
except ImportError:
    class Future: pass
import regexlint.checkers
from regexlint import Regex, run_all_checkers
from regexlint.checkers import manual_check_for_empty_string_match
from regexlint.indicator import find_offending_line, mark, mark_str, find_substr_pos

ONLY_FUNC = None

def import_mod(m):
    mod = __import__(m)
    return sys.modules[m]

def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]

    import optparse
    o = optparse.OptionParser(usage='%prog [options] lexermodule[:class] ...')
    o.add_option('--min_level',
                 help='Min level to print (logging constant names like ERROR)',
                 default='WARNING')
    o.add_option('--output_file',
                 help='Output filename for analysis',
                 default=None)
    o.add_option('--no_parallel',
                 help='Run checks in a single thread',
                 default=True,
                 dest='parallel',
                 action='store_false')
    o.add_option('--only_func',
                 help='Only run this checker func',
                 default=None)
    o.add_option('--regex',
                 help='Check args as regexes instead of Pygments lexers',
                 default=None,
                 action='store_true')
    opts, args = o.parse_args(argv)

    if not args:
        o.error('need some arguments with modules/classes to check')

    min_level = getattr(logging, opts.min_level)
    if opts.output_file:
        output_stream = open(opts.output_file, 'wb')
    else:
        output_stream = sys.stdout
    if opts.only_func:
        global ONLY_FUNC
        ONLY_FUNC = opts.only_func

    if opts.parallel:
        pool = multiprocessing.Pool()
    else:
        pool = itertools

    if opts.regex:
        for result in pool.imap(check_regex_map,
                                [(i, min_level, StringIO()) for i in args]):
            result.seek(0, 0)
            output_stream.write(result.read())
        return

    # currently just a list of module names.
    lexers_to_check = []
    for module in args:
        if ':' in module:
            module, cls = module.split(':')
        else:
            cls = None

        # Support passing a filename instead, since shell completes it.
        if '/' in module and module.endswith('.py'):
            module = module[:-3].replace('/', '.')

        mod = import_mod(module)
        lexers_to_check.append(StringIO("Module %s\n" % module))
        if cls:
            lexers = [cls]
        else:
            if hasattr(mod, '__all__'):
                lexers = mod.__all__
            else:
                lexers = mod.__dict__.keys()

        for k in lexers:
            v = getattr(mod, k)
            if hasattr(v, '__bases__') and issubclass(v, RegexLexer) and v.tokens:
                lexers_to_check.append((k, v, mod.__file__, min_level,
                                        StringIO()))

    for result in pool.imap(check_lexer_map, lexers_to_check):
        result.seek(0, 0)
        output_stream.write(result.read())


def remove_error(errs, *nums):
    for i in range(len(errs)-1, -1, -1):
        if errs[i][0] in nums:
            del errs[i]

def check_regex_map(tup):
    return check_regex(*tup)

def check_regex(regex_text, min_level, output_stream=sys.stdout):
    has_errors = False
    reg = Regex.get_parse_tree(regex_text, 0)
    if ONLY_FUNC:
        errs = []
        getattr(regexlint.checkers, ONLY_FUNC)(reg, errs)
    else:
        errs = run_all_checkers(reg, None)
        # Special case for empty string, since it needs action.
        manual_check_for_empty_string_match(reg, errs, (regex_text, Token))

    errs.sort(key=lambda k: (k[1], k[0]))
    if errs:
        for num, severity, pos1, text in errs:
            if severity < min_level: continue

            # Only set this if we're going to output something --
            # otherwise the [Lexer] OK won't print
            has_errors = True
            line = '#'

            print('%s%s:%s:%s:%s: %s' % (
                logging.getLevelName(severity)[0], num,
                'argv', 'root', 0, text), file=output_stream)
            mark_str(pos1, pos1+1, regex_text, output_stream)
    if not has_errors:
        print(repr(regex_text), 'OK', file=output_stream)

    return output_stream


def check_lexer_map(args):
    if isinstance(args, StringIO):
        return args
    return check_lexer(*args)

def func_code(func):
    try:
        return func.func_code
    except AttributeError:
        return func.__code__

def func_closure(func):
    try:
        return func.func_closure[0].cell_contents
    except AttributeError:
        return func.__closure__[0].cell_contents

def check_lexer(lexer_name, cls, mod_path, min_level, output_stream=sys.stdout):
    #print lexer_name
    #print cls().tokens
    has_errors = False

    bygroups_callback = func_code(bygroups(1))
    for state, pats in cls().tokens.items():
        if not isinstance(pats, list):
            # This is for Inform7Lexer
            print(lexer_name, 'WEIRD', file=output_stream)
            return output_stream

        for i, pat in enumerate(pats):
            if hasattr(pat, 'state'):
                # new 'default'
                continue

            try:
                if isinstance(pat[0], Future):
                    pat = (pat[0].get(),) + pat[1:]
                reg = Regex.get_parse_tree(pat[0], cls.flags)
            except TypeError:
                # Doesn't support _inherit yet.
                continue
            except Exception:
                try:
                    print(pat[0], cls, file=output_stream)
                except: pass
                raise
            # Special problem: display an error if count of args to
            # bygroups(...) doesn't match the number of capture groups
            if callable(pat[1]) and func_code(pat[1]) is bygroups_callback:
                by_groups = func_closure(pat[1])
            else:
                by_groups = None

            if ONLY_FUNC:
                errs = []
                getattr(regexlint.checkers, ONLY_FUNC)(reg, errs)
            else:
                errs = run_all_checkers(reg, by_groups)
                # Special case for empty string, since it needs action.
                manual_check_for_empty_string_match(reg, errs, pat)

            errs.sort(key=lambda k: (k[1], k[0]))
            if errs:
                #print "Errors in", lexer_name, state, "pattern", i
                for num, severity, pos1, text in errs:
                    if severity < min_level: continue

                    # Only set this if we're going to output something --
                    # otherwise the [Lexer] OK won't print
                    has_errors = True

                    foo = find_offending_line(mod_path, lexer_name, state, i,
                                              pos1)
                    if foo:
                        line = 'L' + str(foo[0])
                    else:
                        line = 'pat#' + str(i+1)
                    print('%s%s:%s:%s:%s: %s' % (
                        logging.getLevelName(severity)[0], num,
                        lexer_name, state, line, text), file=output_stream)
                    if foo:
                        mark(*(foo + (output_stream,)))
                    else:
                        mark_str(pos1, pos1+1, pat[0], output_stream)
    if not has_errors:
        print(lexer_name, 'OK', file=output_stream)

    return output_stream


if __name__ == '__main__':
    main()
