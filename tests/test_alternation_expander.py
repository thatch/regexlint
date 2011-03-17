from regexlint.checkers import *
from unittest import TestCase

class BasicTests(TestCase):
    def test_empty(self):
        it = get_alternation_possibilities([[]])
        x = it.next()
        self.assertEquals(x, '')
        self.assertRaises(StopIteration, it.next)

    def test_single(self):
        it = get_alternation_possibilities([[(str, 'a')], [(str, 'b')]])
        x = it.next()
        self.assertEquals(x, 'a')
        x = it.next()
        self.assertEquals(x, 'b')
        self.assertRaises(StopIteration, it.next)

class CheckersDoChecking(TestCase):
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
        print repr(r)
        errs = []
        check_no_empty_alternations(r, errs)
        self.assertEquals(len(errs), 1)

    def test_empty_alternation_in_root(self):
        # special case because linenum is bogus on root.
        r = Regex().get_parse_tree(r'a|')
        print repr(r)
        errs = []
        check_no_empty_alternations(r, errs)
        self.assertEquals(len(errs), 1)

    def test_out_of_order_alternation_in_root(self):
        r = Regex().get_parse_tree(r'a|ab')
        print repr(r)
        errs = []
        check_prefix_ordering(r, errs)
        self.assertEquals(len(errs), 1)
