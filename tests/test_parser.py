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

import sre_constants
import sre_parse
from unittest import TestCase

import pytest
from pygments.token import Other

from regexlint.parser import DIGITS, WHITESPACE, WORD, Node, Regex, fmttree
from regexlint.util import find_all, find_all_by_type, width

SAMPLE_PATTERNS = [
    r"a|b|",
    r"((a(?:b))|)",
    r"[a-bb]",
    r"x*",
    r"x{1,}",
    r"x{,5}?",
    r"(?P<first_char>.)(?P=first_char)*",
]

CHARCLASS_PATTERNS = [
    # Commented for 2 vs 3
    # r'[aa]',
    r"[ab]",
    r"[a-b]",
    r"[\a-\b]",
    r"[a\-b]",
    r"[a-]",
    r"[][]",
    r"[]]",
    r"[^]]",
    r"[\[\]]",
    r"[\w]",
    r"[\w\s\d]",
    r"[^xx]",
    r"[^x\s]",
    r"[^x\D]",
    r"[^x\S]",
    r"[^x\W]",
]


class BasicTests(TestCase):
    def do_it(self, s):
        # for debugging
        for x in Regex().get_tokens_unprocessed(s):
            print(x)
        r = Regex.get_parse_tree(s)
        return r

    def test_badness(self):
        self.do_it("\\\\([\\\\abfnrtv\"\\'?]|x[a-fA-F0-9]{2,4}|[0-7]{1,3})")

    def test_bracket(self):
        self.do_it("[^(\\[\\])]*")

    def test_singleparens(self):
        self.do_it(r"\(")
        self.do_it(r"\)")

    def test_brackets(self):
        r = self.do_it(r"\[")
        print(r)
        r = self.do_it(r"\]")

    def test_find_by_type(self):
        golden = [Node(t=Other.Directive, start=0, parsed_start=0, data="(?mi)")]
        r = Regex.get_parse_tree(r"(?mi)")
        self.assertEqual(golden, list(find_all_by_type(r, Other.Directive)))

    def test_find_all_by_type(self):
        r = Regex.get_parse_tree(r"(?m)(?i)")
        directives = list(find_all_by_type(r, Other.Directive))
        self.assertEqual(2, len(directives))
        self.assertEqual("(?m)", directives[0].data)
        self.assertEqual("(?i)", directives[1].data)

    def test_char_range(self):
        r = Regex.get_parse_tree(r"[a-z]")
        self.assertEqual(1, len(next(find_all_by_type(r, Other.CharClass)).chars))

    def test_end_set_correctly(self):
        r = Regex.get_parse_tree(r"\b(foo|bar)\b")
        self.assertEqual(0, r.start)
        capture = r.children[1]
        foo = capture.children[0].children[0]
        self.assertEqual(3, foo.start)
        self.assertEqual(6, foo.end)
        bar = capture.children[0].children[1]
        self.assertEqual(7, bar.start)
        self.assertEqual(10, bar.end)
        self.assertEqual(13, r.end)

    def test_comment(self):
        r = Regex.get_parse_tree(r"(?#foo)")
        l = list(find_all_by_type(r, Other.Comment))
        self.assertEqual(1, len(l))
        self.assertEqual("(?#foo)", l[0].data)

    def test_width(self):
        r = Regex.get_parse_tree(r"\s(?#foo)\b")
        l = list(find_all(r))[1:]  # skip root
        self.assertEqual([True, False, False], [width(i.type) for i in l])

    def test_repetition_plus(self):
        r = Regex.get_parse_tree(r"x+")
        l = list(find_all(r))[1:]  # skip root
        self.assertEqual(2, len(l))
        # l[0] is Repetition, l[1] is Literal(x)
        self.assertEqual(1, l[0].min)
        self.assertEqual(None, l[0].max)
        self.assertEqual(True, l[0].greedy)

    def test_repetition_curly1(self):
        r = Regex.get_parse_tree(r"x{5,5}?")
        print("\n".join(fmttree(r)))
        l = list(find_all(r))[1:]  # skip root
        self.assertEqual(2, len(l))
        # l[0] is Repetition, l[1] is Literal(x)
        self.assertEqual(5, l[0].min)
        self.assertEqual(5, l[0].max)
        self.assertEqual(False, l[0].greedy)

    def test_repetition_curly2(self):
        r = Regex.get_parse_tree(r"x{2,5}")
        l = list(find_all(r))[1:]  # skip root
        self.assertEqual(2, len(l))
        # l[0] is Repetition, l[1] is Literal(x)
        self.assertEqual(2, l[0].min)
        self.assertEqual(5, l[0].max)
        self.assertEqual(True, l[0].greedy)


class VerboseModeTests(TestCase):
    def test_basic_verbose_parsing(self):
        r = Regex.get_parse_tree(
            r"""(?x)  a   b # comment
                        c
                        d"""
        )
        l = list(find_all(r))[1:]  # skip root
        print("\n".join(fmttree(r)))
        self.assertEqual(5, len(l))
        self.assertEqual((4, 6), (l[1].parsed_start, l[1].start))
        self.assertEqual("d", l[-1].data)
        self.assertEqual((7, 72), (l[-1].parsed_start, l[-1].start))

    def test_escaped_space_parsing(self):
        r = Regex.get_parse_tree(r"\ a")
        l = list(find_all(r))[1:]  # skip root
        print("\n".join(fmttree(r)))
        self.assertEqual(2, len(l))
        self.assertEqual(r"\ ", l[0].data)
        self.assertEqual(Other.Suspicious, l[0].type)

    def test_charclass_parsing(self):
        r = Regex.get_parse_tree(r"[ a]")
        l = list(find_all(r))[1:]  # skip root
        print("\n".join(fmttree(r)))
        self.assertEqual(3, len(l))
        self.assertEqual(r" ", l[1].data)
        self.assertEqual(r"a", l[2].data)

    def test_complex_charclass(self):
        r = Regex.get_parse_tree(r"[]\[:_@\".{}()|;,]")
        l = list(find_all(r))[1:]  # skip root
        print("\n".join(fmttree(r)))
        self.assertEqual(15, len(l))


@pytest.mark.parametrize("pat", SAMPLE_PATTERNS)
def test_reconstruct(pat):
    r = Regex.get_parse_tree(pat)
    rec = r.reconstruct()
    assert pat == rec


SRE_CATS = {
    sre_constants.CATEGORY_SPACE: list(map(ord, WHITESPACE)),
    sre_constants.CATEGORY_DIGIT: list(map(ord, DIGITS)),
    sre_constants.CATEGORY_WORD: list(map(ord, WORD)),
    sre_constants.CATEGORY_NOT_SPACE: sorted(
        set(range(256)) - set(map(ord, WHITESPACE))
    ),
    sre_constants.CATEGORY_NOT_DIGIT: sorted(set(range(256)) - set(map(ord, DIGITS))),
    sre_constants.CATEGORY_NOT_WORD: sorted(set(range(256)) - set(map(ord, WORD))),
}


def expand_sre_in(x):
    for (typ, value) in x:
        if typ in (sre_constants.LITERAL, sre_constants.NOT_LITERAL):
            yield value
        elif typ == sre_constants.RANGE:
            for i in range(value[0], value[1] + 1):
                yield i
        elif typ == sre_constants.CATEGORY:
            for i in SRE_CATS[value]:
                yield i
        elif typ == sre_constants.NEGATE:
            pass
        else:
            raise NotImplementedError("Unknown type %s" % typ)


@pytest.mark.parametrize("pat", CHARCLASS_PATTERNS)
def test_charclass(pat):
    r = Regex().get_parse_tree(pat)
    regexlint_version = r.children[0].matching_character_codes
    sre_parsed = sre_parse.parse(pat)
    print(sre_parsed)
    if isinstance(sre_parsed[0][1], int):
        sre_chars = sre_parsed
    else:
        sre_chars = sre_parsed[0][1]
    print("inner", sre_chars)
    golden = list(expand_sre_in(sre_chars))
    order_matters = True
    try:
        if (
            sre_parsed[0][0] == sre_constants.NOT_LITERAL
            or sre_parsed[0][1][0][0] == sre_constants.NEGATE
        ):
            golden = [i for i in range(256) if i not in golden]
            order_matters = False

    except TypeError:
        pass

    print("sre_parse", golden)
    print("regexlint", regexlint_version)
    if order_matters:
        assert golden == regexlint_version
    else:
        print("extra:", sorted(set(regexlint_version) - set(golden)))
        print("missing:", sorted(set(golden) - set(regexlint_version)))

        assert sorted(golden) == sorted(regexlint_version)
