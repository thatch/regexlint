from unittest import TestCase
from pygments.token import Other

from regexlint.parser import Regex
from regexlint.checkers import find_by_type

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

    def test_find_by_type(self):
        r = Regex().get_parse_tree(r'(?xi)')
        self.assertEquals('(?xi)', find_by_type(r, Other.Directive))

