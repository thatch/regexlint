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

import pytest

from regexlint.charclass import (
    WontOptimize,
    build_output,
    charclass_score,
    simplify_charclass,
)
from regexlint.parser import Regex

EXAMPLES = [
    (r"[a-z]", r"[a-z]"),
    (r"[a-zA-Z0-9_]", r"[\w]"),
    # disabled.
    # (r'[0-9]', r'[\d]'),
    (r"[0-9a-f]", None),
    (r"[\S]", r"[\S]"),
    (r"[\S\n]", r"[\S\n]"),
    (r"[^a-zA-Z0-9_]", r"[\W]"),
    (r"[^a-zA-Z0-9]", r"[\W_]"),
    (r"[^\S\n]", r"[\t\x0b\x0c\r ]"),  # Double negative
    (r"[\r\n]", r"[\r\n]"),
    (r"[01]", r"[01]"),
    (r"[0-1]", r"[01]"),
    (r"[a-zA-Z]", r"[a-zA-Z]"),
    (r"(?i)[a-zA-Z]", r"[a-z]"),
    (r"(?i)[a-z0-9_]", r"[\w]"),
    (r"(?i)[A-Z0-9_]", r"[\w]"),
    (r'(?i)[^a-z"/]', r'[^a-z"/]'),
    (r"[\x00-\xff]", r"[\w\W]"),
]


def first_charclass(reg_text):
    r = Regex().get_parse_tree(reg_text, 0)
    return r.children[-1]


def effective_flags(reg_text):
    return Regex().get_parse_tree(reg_text, 0).effective_flags


@pytest.mark.parametrize("the_input, the_output", EXAMPLES)
def test_examples(the_input, the_output):
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
    print("new_codes", new_codes)
    print("new_score", new_score, "expected_score", expected_score)
    print("built", repr(build_output(new_codes)))
    assert new_score == expected_score


def test_match_everything():
    new_codes, negated = simplify_charclass(range(256))
    assert new_codes == ["\\w", "\\W"]
    assert not negated


def test_caret_escaping1():
    new_codes, negated = simplify_charclass([ord("^")])
    print(new_codes)
    assert len(new_codes) == 1
    assert not negated
    op = build_output(new_codes)
    assert op == "\\^"


def test_caret_escaping2():
    new_codes, negated = simplify_charclass([ord("^"), ord("]")])
    print(new_codes)
    assert len(new_codes) == 2
    assert not negated
    op = build_output(new_codes)
    assert op == "\\]\\^"
