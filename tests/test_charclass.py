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

import re
from unittest import TestCase

from regexlint.parser import Regex
from regexlint.charclass import *

EXAMPLES = [
    (r'[a-z]', r'[a-z]'),
    (r'[a-zA-Z0-9_]', r'[\w]'),
    (r'[0-9]', r'[\d]'),
    (r'[0-9a-f]', None),
    (r'[\S]', r'[\S]'),
    (r'[\S\n]', r'[\S\n]'),
    (r'[^a-zA-Z0-9_]', '[\W]'),
    (r'[^a-zA-Z0-9]', '[\W_]'),
    (r'[^\S\n]', r'[\t\x0b\x0c\r ]'),  # Double negative
    (r'[\r\n]', r'[\r\n]'),
    (r'[01]', r'[01]'),
    (r'[0-1]', r'[01]'),
    (r'[a-zA-Z]', r'[a-zA-Z]'),
    (r'(?i)[a-zA-Z]', r'[a-z]'),
    (r'(?i)[a-z0-9_]', r'[\w]'),
    (r'(?i)[A-Z0-9_]', r'[\w]'),
    (r'[\x00-\xff]', r'[\w\W]'),
]

def test_examples():
    for a, b in EXAMPLES:
        yield runner, a, b

def first_charclass(reg_text):
    r = Regex().get_parse_tree(reg_text, 0)
    return r.children[-1]

def effective_flags(reg_text):
    return Regex().get_parse_tree(reg_text, 0).effective_flags

def runner(the_input, the_output):
    cc = first_charclass(the_input)
    codes = cc.matching_character_codes
    ignorecase = bool(effective_flags(the_input) & re.IGNORECASE)

    try:
        new_codes, negated = simplify_charclass(codes, ignorecase=ignorecase)
    except WontOptimize:
        assert the_output is None
        return

    new_score = charclass_score(new_codes, negated)

    expected_score = charclass_score(first_charclass(the_output))
    print "new_codes", new_codes
    print "new_score", new_score, "expected_score", expected_score
    print "built", repr(build_output(new_codes))
    assert new_score == expected_score
