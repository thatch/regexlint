# Copyright 2012-2014 Google Inc.
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

import re
from regexlint.util import rindex

strp = {
    '': re.compile(r'\\(?:[\\abfnrtv"\']|\n|x[a-fA-F0-9]{2}|[0-7]{1,3})|'
                   r'[\w\W]'),
    'u': re.compile(r'\\(?:[\\abfnrtv"\']|\n|N{.*?}|u[a-fA-F0-9]{4}|'
                    r'U[a-fA-F0-9]{8}|x[a-fA-F0-9]{2}|[0-7]{1,3})|[\w\W]'),
    'r': re.compile(r'[\w\W]'),
    'ur': re.compile(r'\\(?:\\|u[a-fA-F0-9]{4}|U[a-fA-F0-9]{8})|[\w\W]'),
}

def find_substr_pos(s, target):
    if s[-3:] in ('"""', "'''"):
        end_quote = s[-3:]
    else:
        end_quote = s[-1]
    p = s.find(end_quote)
    mods = s[:p]
    body = s[p+len(end_quote):-len(end_quote)]

    chars = strp[mods].findall(body)
    if 'r' not in mods:
        # hack to support a zero-width escape sequence -- escaped newline
        for i in range(len(chars)):
            if chars[i] == '\\\n':
                target += 1
            if i >= target: break

    if target >= len(chars) or target < 0:
        raise ValueError("Impossible, out of bounds")

    l = 0
    q = p+len(end_quote)+sum(map(len, chars[:target]))

    # only for triplequoted strings
    if '\n' in chars[:target]:
        #print "GOT", target, chars[:target]
        l = chars[:target].count('\n')
        _ = rindex(chars[:target], '\n') + 1
        #print "_", _
        q = sum(map(len, chars[_:target]))
        #print "q", l, q, q+len(chars[target])

    #print q
    return (l, q, q+len(chars[target]))

