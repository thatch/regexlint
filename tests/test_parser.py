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

from unittest import TestCase
from pygments.token import Other

from regexlint.parser import Regex
from regexlint.checkers import find_all_by_type

class BasicTests(TestCase):
    def do_it(self, s):
        # for debugging
        for x in Regex().get_tokens_unprocessed(s):
            print x
        r = Regex().get_parse_tree(s)
        return r

    def test_badness(self):
        self.do_it('\\\\([\\\\abfnrtv"\\\'?]|x[a-fA-F0-9]{2,4}|[0-7]{1,3})')
    def test_bracket(self):
        self.do_it('[^(\\[\\])]*')

    def test_singleparens(self):
        self.do_it(r'\(')
        self.do_it(r'\)')

    def test_brackets(self):
        r = self.do_it(r'\[')
        print r
        r = self.do_it(r'\]')

    def test_find_by_type(self):
        r = Regex().get_parse_tree(r'(?xi)')
        self.assertEquals(['(?xi)'], list(find_all_by_type(r, Other.Directive)))

    def test_find_all_by_type(self):
        r = Regex().get_parse_tree(r'(?x)(?i)')
        self.assertEquals(2, len(list(find_all_by_type(r, Other.Directive))))

    def test_char_range(self):
        r = Regex().get_parse_tree(r'[a-z]')
        self.assertEquals(1, len(r.alternations[0][0][1].chars))

    def test_end_set_correctly(self):
        r = Regex().get_parse_tree(r'\b(foo|bar)\b')
        print id(r)
        print id(r.alternations[0][1][1])
        self.assertEquals(0, r.start)
        self.assertEquals(2, r.alternations[0][1][1].start)
        self.assertEquals(11, r.alternations[0][1][1].end)
        self.assertEquals(13, r.end)
