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

from regexlint.checkers import *
from regexlint.parser import fmttree
from unittest import TestCase

class CheckersTests(TestCase):
    def test_null(self):
        r = Regex().get_parse_tree('a\x00b')
        errs = []
        check_no_nulls(r, errs)
        self.assertEquals(len(errs), 1)

    def test_newline(self):
        r = Regex().get_parse_tree('a\nb')
        errs = []
        check_no_newlines(r, errs)
        self.assertEquals(len(errs), 1)

    def test_empty_alternation(self):
        r = Regex().get_parse_tree(r'(a|)')
        print '\n'.join(fmttree(r))
        errs = []
        check_no_empty_alternations(r, errs)
        self.assertEquals(len(errs), 1)

    def test_empty_alternation_in_root(self):
        # special case because linenum is bogus on root.
        r = Regex().get_parse_tree(r'a|')
        print '\n'.join(fmttree(r))
        errs = []
        check_no_empty_alternations(r, errs)
        self.assertEquals(len(errs), 1)

    def test_out_of_order_alternation_in_root(self):
        r = Regex().get_parse_tree(r'a|ab')
        print '\n'.join(fmttree(r))
        errs = []
        check_prefix_ordering(r, errs)
        self.assertEquals(len(errs), 1)

    def test_out_of_order_crazy_complicated(self):
        r = Regex().get_parse_tree(r'''(!=|#|&&|&|\(|\)|\*|\+|,|-|-\.)''')
        #|->|\.|\.\.|::|:=|:>|:|;;|;|<|<-|=|>|>]|>}|\?|\?\?|\[|\[<|\[>|\[\||]|_|`|{|{<|\||\|]|}|~)''')
        print '\n'.join(fmttree(r))
        errs = []
        check_prefix_ordering(r, errs)
        self.assertEquals(len(errs), 1)

    def test_good_charclass(self):
        r = Regex().get_parse_tree(r'[a-zA-Z]')
        print '\n'.join(fmttree(r))
        errs = []
        check_charclass_homogeneous_ranges(r, errs)
        self.assertEquals(len(errs), 0)

    def test_bad_charclass(self):
        r = Regex().get_parse_tree(r'[A-z]')
        print '\n'.join(fmttree(r))
        print r.children[0].chars
        errs = []
        check_charclass_homogeneous_ranges(r, errs)
        print errs
        self.assertEquals(len(errs), 1)

    def test_bad_charclass2(self):
        r = Regex().get_parse_tree(r'[z-A]')
        print '\n'.join(fmttree(r))
        print r.children[0].chars
        errs = []
        check_charclass_homogeneous_ranges(r, errs)
        print errs
        self.assertEquals(len(errs), 2)
