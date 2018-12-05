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
from __future__ import print_function
from __future__ import unicode_literals

import sys
import nose.plugins.skip
from unittest import TestCase

from regexlint.util import *

class UtilTests(TestCase):
    def test_eval_char_canonical_ascii(self):
        for i in range(256):
            char = chr(i)
            actual = eval_char(repr(char)[1:-1])
            self.assertEqual(i, actual)

    def test_eval_char_numeric(self):
        for c in (b'\x40', b'\100', '\u0040', '@', '\\@', '\\x40', '\\100',
                  '\\u0040', '\\U00000040'):
            print(c)
            actual = eval_char(c)
            self.assertEqual(actual, 0x40)

    def test_consistent_repr_empty(self):
        golden = r"''"
        self.assertEqual(golden, consistent_repr(eval(golden)))

    def test_consistent_repr(self):
        golden = r"""b'azAZ09!#-$_\\/\'"\n\t\x02\xf3'"""
        self.assertEqual(golden, consistent_repr(eval(golden)))

    def test_consistent_repr_unicode(self):
        golden = "'text\\u1234text'"
        print(repr(eval(golden)))
        self.assertEqual(len(golden), len(consistent_repr(eval(golden))))
        self.assertEqual(golden, consistent_repr(eval(golden)))

    def test_consistent_repr_wide_unicode(self):
        if sys.maxunicode < 65536:
            # Python build doesn't handle 32-bit unicode
            raise nose.plugins.skip.SkipTest('narrow python build')
        else:
            # Python build handles 32-bit unicode
            golden = u"'text\\U00101234text'"
            print(repr(eval(golden)))
            self.assertEqual(len(golden), len(consistent_repr(eval(golden))))
            self.assertEqual(golden, consistent_repr(eval(golden)))

    def test_consistent_repr_for_ranges(self):
        r = consistent_repr('a-b[]', escape='[]-', include_quotes=False)
        self.assertEqual(r, r'a\-b\[\]')


class RangesTest(TestCase):
    def test_disjoint(self):
        self.assertEqual([65, 67, 69], build_ranges([65, 67, 69]))
    def test_joint(self):
        self.assertEqual([(65, 66), 69], build_ranges([65, 66, 69]))
