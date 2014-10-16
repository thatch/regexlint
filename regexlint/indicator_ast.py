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
This uses the python ast module to find the positions of strings in the source
file.  Due to what appear to be bugs in the ast module when a string spans
lines, this is not the default.
"""

import re
import ast

from regexlint.indicator_substr import find_substr_pos
from regexlint.util import get_module_text

try:
    enumerate((), 1)
except TypeError:
    # Py25 compat
    def enumerate(l, start=None):
        i = start or 0
        for x in l:
            yield i, x
            i += 1

parse_cache = {}

def find_offending_line(mod, clsname, state, idx, pos):
    """
    Returns a tuple of (lineno, charpos_start, charpos_end, line_content)
    """
    try:
        mod_text, tree = parse_cache[mod]
    except KeyError:
        mod_text = get_module_text(mod)
        tree = ast.parse(mod_text)
        parse_cache[mod] = mod_text, tree

    klass = None
    for item in ast.walk(tree):
        if isinstance(item, ast.ClassDef):
            if clsname == item.name:
                klass = item
                break
    if not klass:
        return
    for item in ast.walk(klass):
        if not isinstance(item, ast.Dict):
            continue
        stateValue = None
        for i, key in enumerate(item.keys):
            if isinstance(key, ast.Str) and key.s == state:
                stateValue = item.values[i]
        if stateValue == None:
            continue
        if not isinstance(stateValue, ast.List):
            continue
        if not idx < len(stateValue.elts):
            continue
        idxTuple = stateValue.elts[idx]
        if not isinstance(idxTuple, ast.Tuple):
            continue
        if len(idxTuple.elts) < 2 or not isinstance(idxTuple.elts[0], ast.Str):
            continue
        lines = []
        startline = idxTuple.elts[0].lineno - 1
        startchar = idxTuple.elts[0].col_offset
        stopline = idxTuple.elts[1].lineno
        stopchar = idxTuple.elts[1].col_offset

        #print "Block"
        #print idxTuple.col_offset, idxTuple.elts[0].col_offset, idxTuple.elts[1].col_offset
        #print idxTuple.lineno, idxTuple.elts[0].lineno, idxTuple.elts[1].lineno
        #print mod_text.splitlines()[idxTuple.lineno-1]

        # HACK HACK HACK
        if idxTuple.elts[0].col_offset == -1:
            # When col_offset==-1 then the string is split across multiple
            # lines. This generally means it's a triplequoted string, which
            # can be located with a dumb heuristic.
            _lines = mod_text.splitlines()
            if '"""' in _lines[startline]:
                target = '"""'
            elif "'''" in _lines[startline]:
                target = "'''"
            else:
                #print "Cannot locate beginning string"
                return None

            for i in range(startline-1, -1, -1):
                if target in _lines[i]:
                    #print "Adjusted start line from", startline, "to", i
                    startline = i
                    startchar = _lines[i].rindex(target) - 2 # for 'ur'
                    break

        # END HACK

        for i, line in enumerate(mod_text.splitlines()[startline:], startline):
            if i == stopline:
                line = line[:stopchar]
            if i == startline:
                line = line[startchar:]
            lines.append(line)
            if i >= stopline:
                break
        rawstr = "\n".join(lines)

        strRe = re.compile("[uU]?[rR]?(?:"
            "'''(?:[^\\\\]|\\\\.)*?'''|"
            '"""(?:[^\\\\]|\\\\.)*?"""|'
            "'(?:[^\\\\]|\\\\.)*?'|"
            '"(?:[^\\\\]|\\\\.)*?"'
            ")", re.DOTALL)
        #print "rawstr:", repr(rawstr)
        for match in strRe.finditer(rawstr):
            #print "match:", repr(match.group(0))
            strInst = match.group(0)
            try:
                (dx, d1, d2) = find_substr_pos(strInst, pos)
            except ValueError:
                pos -= len(eval(strInst))
                continue
            before_match = rawstr[:match.start(0)]
            match_lineno_in_rawstr = before_match.count("\n")
            lineno = startline + 1 + match_lineno_in_rawstr
            col_offset = match.start(0) - (before_match.rfind("\n") + 1)
            if match_lineno_in_rawstr == 0:
                col_offset += startchar
            if dx == 0:
                d1 += col_offset
                d2 += col_offset
            return (lineno+dx, d1, d2,
                    mod_text.splitlines()[lineno+dx-1])
