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

import re
import unittest
from io import StringIO

from regexlint.indicator import find_offending_line, find_substr_pos, mark_str

fakemod = r'''# line 1
class foo(object):
    flags = re.MULTILINE
    tokens = {
        'root': [
            (r'grr', Token.Root),
        ],
        'other': [
            (r'bar', String),
            (r'baz'
             u'\x00hi', Other),
            (r"""foo
newlines1
newlines2""", Other),
        ],
        'char': stringy(String.Char),
        'string': stringy(String.Double),
        'breakout': [
            (r'abcdefg', Text),
        ],
        'evil': func({'foo': 'bar', 'baz': [('a', String)]}),
        'baz': [('b', String)],
    }
'''


class IndicatorTests(unittest.TestCase):
    def test_find_offending_line_1(self):
        ret = find_offending_line(fakemod, "foo", "root", 0, 0)
        self.assertEqual((6, 15, 16, "            (r'grr', Token.Root),"), ret)

    def test_find_offending_line_more_complex1(self):
        ret = find_offending_line(fakemod, "foo", "other", 1, 3)
        self.assertEqual((11, 15, 19, r"             u'\x00hi', Other),"), ret)
        self.assertEqual(r"\x00", ret[3][ret[1] : ret[2]])

    def test_find_offending_line_more_complex2(self):
        ret = find_offending_line(fakemod, "foo", "other", 1, 4)
        self.assertEqual((11, 19, 20, r"             u'\x00hi', Other),"), ret)
        self.assertEqual("h", ret[3][ret[1] : ret[2]])

    def test_find_offending_line_newline_triplequote1(self):
        ret = find_offending_line(fakemod, "foo", "other", 2, 0)
        self.assertEqual((12, 17, 18, '            (r"""foo'), ret)

    def test_find_offending_line_newline_triplequote2(self):
        ret = find_offending_line(fakemod, "foo", "other", 2, 3)
        self.assertEqual((12, 20, 21, '            (r"""foo'), ret)

    def test_find_offending_line_newline_triplequote3(self):
        ret = find_offending_line(fakemod, "foo", "other", 2, 4)
        self.assertEqual((13, 0, 1, "newlines1"), ret)

    def test_find_offending_line_in_function(self):
        # Based off a real failure in p.l.functional:SMLLexer
        ret = find_offending_line(fakemod, "foo", "char", 2, 5)
        self.assertEqual(None, ret)

    def test_find_offending_line_after_comma(self):
        # Ignore commas that might occur in function calls.
        ret = find_offending_line(fakemod, "foo", "baz", 0, 0)
        self.assertEqual((22, 18, 19, "        'baz': [('b', String)],"), ret)


class SubstrPosTests(unittest.TestCase):
    def test_find_pos1(self):
        r = find_substr_pos('u"abc"', 0)
        self.assertEqual((0, 2, 3), r)

    def test_find_pos2(self):
        r = find_substr_pos('u"abc"', 1)
        self.assertEqual((0, 3, 4), r)

    def test_find_pos3(self):
        r = find_substr_pos('u"abc"', 2)
        self.assertEqual((0, 4, 5), r)

    def test_find_pos_escapes(self):
        r = find_substr_pos(r'u"a\u1234b"', 1)
        self.assertEqual((0, 3, 9), r)

    def test_find_pos_octal(self):
        s = r'"\000b"'
        r = find_substr_pos(s, 0)
        print(s[r[0] : r[1]])
        self.assertEqual((0, 1, 5), r)

    def test_find_pos_end(self):
        r = find_substr_pos('"a"', 0)
        self.assertEqual((0, 1, 2), r)

    def test_find_impossible(self):
        self.assertRaises(ValueError, find_substr_pos, '"a"', 1)

    def test_trailing_newline(self):
        r = find_substr_pos(r'"a\n"', 1)
        self.assertEqual((0, 2, 4), r)

    def test_unicode_difference(self):
        r = find_substr_pos(r'u"\u1234foo"', 1)
        self.assertEqual((0, 8, 9), r)
        r = find_substr_pos(r'"\u1234foo"', 1)
        self.assertEqual((0, 2, 3), r)

    def test_named(self):
        r = find_substr_pos(r'u"\N{space}foo"', 0)
        self.assertEqual((0, 2, 11), r)
        r = find_substr_pos(r'u"\N{space}foo"', 1)
        self.assertEqual((0, 11, 12), r)
        r = find_substr_pos(r'"\N{space}foo"', 1)
        self.assertEqual((0, 2, 3), r)

    def test_tripled(self):
        r = find_substr_pos(r'"""a\x00"""', 1)
        self.assertEqual((0, 4, 8), r)

    def test_find_pos_newline(self):
        r = find_substr_pos("'\\\na'", 0)
        self.assertEqual((0, 3, 4), r)

    def test_find_pos_raw_backslash(self):
        r = find_substr_pos(r'r"\\"', 1)
        self.assertEqual((0, 3, 4), r)


class MarkStrTest(unittest.TestCase):
    def _test(self, input, substr_repr, substr=None):
        if substr is None:
            substr = substr_repr
        buf = StringIO()
        pos1 = input.index(substr)
        pos2 = pos1 + len(substr)
        mark_str(pos1, pos2, input, buf)
        output = buf.getvalue()
        self.assertEqual(substr_repr, underlined_part(output))

    def test_mark_str_left(self):
        # this doesn't need shortening
        self._test("abcd", "a")

    def test_mark_str_middle(self):
        self._test("a" * 1000 + "b" + "c" * 1000, "b")

    def test_mark_unicode(self):
        self._test(u"a" * 1000 + u"\u1234", "\\u1234", u"\u1234")


class UnderlineHelperTest(unittest.TestCase):
    def test_underline_single(self):
        s = """\
abcdef
  ^\
"""
        self.assertEqual("c", underlined_part(s))

    def test_underline_multi(self):
        s = """\
abcdef
 ^^^  \
"""
        self.assertEqual("bcd", underlined_part(s))


def underlined_part(s, underline_char="^"):
    """Return the part of `s` that is underlined.

    Given a multiline string, return the part of the first line that has
    underline_char on the second line.
    """
    lines = s.splitlines()
    underline_re = re.compile(re.escape(underline_char) + "+")
    m = underline_re.search(lines[1])
    if not m:
        raise ValueError("String %r has no underline" % (s,))
    return lines[0][m.start() : m.end()]
