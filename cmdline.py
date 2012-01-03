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
from regexlint.indicator import find_offending_line, mark, find_substr_pos

def import_mod(m):
    mod = __import__(m)
    for part in m.split('.')[1:]:
        mod = getattr(mod, part)
    return mod

def main(argv):
    import optparse
    o = optparse.OptionParser()
    o.add_option('--min_level',
                 help='Min level to print (logging constant names like ERROR)',
                 default='ERROR')
    opts, args = o.parse_args(argv)

    min_level = getattr(logging, opts.min_level)

    # currently just a list of module names.
    for module in args:
        if ':' in module:
            module, cls = module.split(':')
        else:
            cls = None
        mod = import_mod(module)
        print "Module", module
        if cls:
            lexers = [cls]
        else:
            if hasattr(mod, '__all__'):
                lexers = mod.__all__
            else:
                lexers = mod.__dict__.keys()

        check_lexers(mod, lexers, min_level=min_level)

def check_lexers(mod, lexer_names, min_level):
    for k in lexer_names:
        v = getattr(mod, k)
        if hasattr(v, '__bases__') and issubclass(v, RegexLexer) and v.tokens:
            check_lexer(k, v, mod.__file__, min_level)

def shorten(text, start, end):
    if len(text) < 76:
        return (text, start, end)

    start_cut = max(0, start - 36)
    end_cut = min(len(text), start + 36)
    cut_text = text[start_cut:end_cut]
    start -= start_cut
    end -= start_cut
    if start_cut != 0:
        cut_text = '...' + cut_text
        start += 3
        end += 3
    if end_cut != len(text):
        cut_text += '...'
    return (cut_text, start, end)

def myrepr(s):
    special = {
        '\n': '\\n',
        '\t': '\\t',
        '\\': '\\\\',
        '\'': '\\\'',
    }
    rep = ['\'']
    if isinstance(s, unicode):
        rep.insert(0, 'u')
    for char in s:
        if char in special:
            rep.append(special[char])
        elif isinstance(s, unicode) and ord(char) > 0xFFFF:
            rep.append('\\U%08x' % ord(char))
        elif isinstance(s, unicode) and ord(char) > 126:
            rep.append('\\u%04x' % ord(char))
        elif ord(char) < 32 or ord(char) > 126:
            rep.append('\\x%02x' % ord(char))
        else:
            rep.append(char)
    rep.append('\'')
    return ''.join(rep)

def remove_error(errs, *nums):
    for i in range(len(errs)-1, -1, -1):
        if errs[i][0] in nums:
            del errs[i]

def check_lexer(lexer_name, cls, mod_path, min_level):
    #print lexer_name
    #print cls().tokens
    has_errors = False
    if cls.flags & re.VERBOSE:
        print "GRR", lexer_name, "uses verbose mode"
        return

    bygroups_callback = bygroups(1).func_code
    for state, pats in cls().tokens.iteritems():
        for i, pat in enumerate(pats):
            #print repr(pat[0])
            try:
                reg = Regex().get_parse_tree(pat[0])
            except:
                print pat[0], cls
                raise
            # TODO check for verbose mode here.
            # Special problem: display an error if count of args to
            # bygroups(...) doesn't match the number of capture groups
            bygroups_callback = bygroups(1).func_code
            if callable(pat[1]) and pat[1].func_code is bygroups_callback:
                num_groups = len(pat[1].__closure__[0].cell_contents)
            else:
                num_groups = None

            errs = run_all_checkers(reg, num_groups)
            # Note, things like '#pop' and 'next-state' get a pass on this, as
            # do callback functions, since they are mostly used for advanced
            # features in indent-dependent languages.
            if len(pat) < 3 and isinstance(pat[1], Token):
                if re.compile(pat[0]).match(''):
                    errs.append(('999', logging.ERROR, 'Matches empty string'))
                #remove_error(errs, '103')

            errs.sort(key=lambda k: (k[1], k[0]))
            if errs:
                has_errors = True
                #print "Errors in", lexer_name, state, "pattern", i
                for num, severity, pos1, text in errs:
                    if severity < min_level: continue
                    foo = find_offending_line(mod_path, lexer_name, state, i, pos1)
                    if foo:
                        line = 'L' + str(foo[0])
                    else:
                        line = 'pat#' + str(i+1)
                    print '%s%s:%s:%s:%s: %s' % (
                        logging.getLevelName(severity)[0], num,
                        lexer_name, state, line, text)
                    if foo:
                        mark(*foo)
                    else:
                        # Substract one for closing quote
                        start = len(myrepr(pat[0][:pos1])) - 1
                        end = len(myrepr(pat[0][:pos1+1])) - 1
                        if start == end:
                            # This handles the case where pos1 points to the end of
                            # the string. Regex "|" with pos1 = 1.
                            end += 1
                        assert end > start
                        text, start, end = shorten(repr(pat[0]), start, end)
                        mark(-1, start, end, text)
    if not has_errors:
        print lexer_name, "OK"


if __name__ == '__main__':
    main(sys.argv[1:])
