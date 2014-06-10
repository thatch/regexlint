# Copyright 2011-2014 Google Inc.
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

"""
This script is several layered hacks to be able to point out clang-style errors
for a specific line of Python code (likely in a string literal).  Do not take
as an example of well-written Python.
"""
import re

from pygments.lexers.agile import PythonLexer
from pygments.token import Punctuation, Name, Text, String

from regexlint.indicator_substr import find_substr_pos
from regexlint.util import get_module_text

R_CLASSEXTRACT = re.compile(r'class (\w+).*:\n([\w\W]*?)(?=^class|\Z)', re.MULTILINE)

open_braces = '[{('
close_braces = ']})'


def find_offending_line(mod, clsname, state, idx, pos):
    """
    Returns a tuple of (lineno, charpos_start, charpos_end, line_content)
    """
    mod_text = get_module_text(mod)

    # skip as far as possible using regular expressions, then start lexing.
    for m in R_CLASSEXTRACT.finditer(mod_text):
        #print "Got class", m.group(1), '...' + repr(m.group(0)[-40:])
        if m.group(1) == clsname: break
    else:
        return None
        #raise ValueError("Can't find class %r" % (clsname,))

    def match_brace(brace):
        target = close_braces[open_braces.index(brace)]
        #print "matching brace", brace, target, it
        for x in it:
            #print x
            if x[-2] in Punctuation and x[-1] == target:
                #print "  found"
                return True
            elif x[-2] in Punctuation and x[-1] in open_braces:
                # begin again!
                if not match_brace(x[-1]):
                    #print "  fail2"
                    return False
        #print "  inner fail"
        return False

    def until(t, match_braces=False):
        #print "until", t
        for x in it:
            if t == x[-1]:
                #print "  found", repr(x[-1])
                return
            elif match_braces and x[-1] in open_braces:
                match_brace(x[-1])

    level = 0
    tuple_idx = 0
    string_pos = 0

    def amal(i):
        si = None
        pt = None
        pd = None
        for idx, tok, data in i:
            if tok in String: tok = String
            if tok == pt == String:
                pd += data
            else:
                if pt:
                    yield si, pt, pd
                pt = tok
                pd = data
                si = idx
        if pt:
            yield si, pt, pd

    def filt(i):
        line = 1 + mod_text[:m.start()].count('\n')
        col = 0
        for _, b, c in i:
            #print "got", b, repr(c)
            yield line, col, b, c
            line += c.count('\n')
            if '\n' in c:
                col = len(c) - c.rindex('\n') - 1
            else:
                col += len(c)

    it = filt(amal(PythonLexer().get_tokens_unprocessed(m.group(0))))

    for x, y, ttyp, text in it:
        #print "Loop", level, ttyp, repr(text)
        if level == 0 and ttyp is Name:
            if text == 'tokens':
                until('=')
                until('{')
                level = 1
        elif level == 1 and ttyp in String:
            #print "key", text
            key = eval(text, {}, {})

            # next is expected to be the colon.
            it.next()
            # next is either a left brace, or maybe a function call
            t = ''
            try:
                while not t.strip():
                    _, _, _, t = it.next()
            except StopIteration:
                return None
            # t is now the first token of the value, either '[' or 'SomeFunc'

            if key != state:
                if t == '[':
                    match_brace('[')
                else:
                    until(',', match_braces=True)
            else:
                level = 2
                if t != '[':
                    return None
        elif level == 2:
            if text == '(':
                # open a tuple
                level = 3
            elif text == ')':
                level = 1 # honestly this should be able to just return
                #print "too late", idx, tuple_idx
                return
        elif level == 3:
            #print "  idx", tuple_idx
            if text == ')':
                level = 2
                tuple_idx += 1
            elif text == '(':
                match_brace('(')
            elif tuple_idx == idx and ttyp in String:
                # this might be it!
                s = eval(text, {}, {})
                #print "maybe", string_pos, pos, (string_pos+len(s))
                if string_pos <= pos < (string_pos+len(s)):
                    # need to point in here
                    (dx, d1, d2) = find_substr_pos(text, pos - string_pos)
                    if dx == 0:
                        d1 += y
                        d2 += y
                    return (x+dx, d1, d2, mod_text.splitlines()[x+dx-1])
                else:
                    string_pos += len(s)
            elif tuple_idx == idx and ttyp in Name:
                # If they're concatenating strings with vars, ignore.
                break

