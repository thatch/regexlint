#!/usr/bin/env python2
#
# Copyright 2011 Google Inc.
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

import sys
import re
import logging

from pygments.lexer import RegexLexer, bygroups
from pygments.token import Token
from regexlint import Regex, run_all_checkers
from regexlint.indicator import find_offending_line, mark
from regexlint.checkers import manual_toknum

def import_mod(m):
    mod = __import__(m)
    for part in m.split('.')[1:]:
        mod = getattr(mod, part)
    return mod

def main(argv):
    # currently just a list of module names.
    for module in argv:
        mod = import_mod(module)
        print "Module", module
        if hasattr(mod, '__all__'):
            check_lexers(mod, mod.__all__)
        else:
            check_lexers(mod, mod.__dict__.keys())

def check_lexers(mod, lexer_names):
    for k in lexer_names:
        v = getattr(mod, k)
        if hasattr(v, '__bases__') and issubclass(v, RegexLexer) and v.tokens:
            check_lexer(k, v, mod.__file__)

def shorten(s):
    if len(s) < 76:
        return repr(s)
    else:
        return repr(s)[:72] + '...'

def remove_error(errs, *nums):
    for i in range(len(errs)-1, -1, -1):
        if errs[i][0] in nums:
            del errs[i]

def check_lexer(lexer_name, cls, mod_path):
    #print lexer_name
    #print cls().tokens
    has_errors = False
    if cls.flags & re.VERBOSE:
        print "GRR", lexer_name, "uses verbose mode"
        return
    for state, pats in cls().tokens.iteritems():
        for i, pat in enumerate(pats):
            #print repr(pat[0])
            try:
                reg = Regex().get_parse_tree(pat[0])
            except:
                print pat[0], cls
                raise
            # TODO check for verbose mode here.
            errs = run_all_checkers(reg)
            # Note, things like '#pop' and 'next-state' get a pass on this, as
            # do callback functions, since they are mostly used for advanced
            # features in indent-dependent languages.
            if len(pat) < 3 and isinstance(pat[1], Token):
                if re.compile(pat[0]).match(''):
                    errs.append(('999', logging.ERROR, 'Matches empty string'))
                #remove_error(errs, '103')


            # Special problem: display an error if count of args to
            # bygroups(...) doesn't match the number of capture groups
            bygroups_callback = bygroups(1).func_code
            if callable(pat[1]) and pat[1].func_code is bygroups_callback:
                num_groups = len(pat[1].__closure__[0].cell_contents)
                manual_toknum(reg, errs, num_groups)

            errs.sort(key=lambda k: (k[1], k[0]))
            if errs:
                has_errors = True
                #print "Errors in", lexer_name, state, "pattern", i
                for num, severity, pos1, text in errs:
                    foo = find_offending_line(mod_path, lexer_name, state, i, pos1)
                    if foo:
                        line = 'L' + str(foo[0])
                    else:
                        line = 'pat#' + str(i+1)
                    print '%s%s:%s:%s:%s: %s' % (
                        (severity >= logging.ERROR and 'E' or 'W'), num,
                        lexer_name, state, line, text)
                    if foo:
                        mark(*foo)
                    else:
                        print 'Y  ' + shorten(pat[0])
    if not has_errors:
        print lexer_name, "OK"


if __name__ == '__main__':
    main(sys.argv[1:])
