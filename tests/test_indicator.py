import unittest

from regexlint.indicator import *

fakemod = \
r'''# line 1
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
        ],
    }
'''

class IndicatorTests(unittest.TestCase):
    def test_find_offending_line_1(self):
        ret = find_offending_line(fakemod, 'foo', 'root', 0, 0)
        self.assertEquals((6, 15, 16, "            (r'grr', Token.Root),"), ret)
    def test_find_offending_line_more_complex1(self):
        ret = find_offending_line(fakemod, 'foo', 'other', 1, 3)
        self.assertEquals((11, 15, 19, r"             u'\x00hi', Other),"), ret)
        self.assertEquals(r"\x00", ret[3][ret[1]:ret[2]])
    def test_find_offending_line_more_complex2(self):
        ret = find_offending_line(fakemod, 'foo', 'other', 1, 4)
        self.assertEquals((11, 19, 20, r"             u'\x00hi', Other),"), ret)
        self.assertEquals("h", ret[3][ret[1]:ret[2]])



class SubstrPosTests(unittest.TestCase):
    def test_find_pos1(self):
        r = find_substr_pos('u"abc"', 0)
        self.assertEquals((2, 3), r)
    def test_find_pos2(self):
        r = find_substr_pos('u"abc"', 1)
        self.assertEquals((3, 4), r)
    def test_find_pos3(self):
        r = find_substr_pos('u"abc"', 2)
        self.assertEquals((4, 5), r)
    def test_find_pos_escapes(self):
        r = find_substr_pos(r'u"a\u1234b"', 1)
        self.assertEquals((3, 9), r)
    def test_find_pos_octal(self):
        s = r'"\000b"'
        r = find_substr_pos(s, 0)
        print s[r[0]:r[1]]
        self.assertEquals((1, 3), r)
    def test_find_pos_end(self):
        r = find_substr_pos('"a"', 0)
        self.assertEquals((1, 2), r)
    def test_find_impossible(self):
        self.assertRaises(ValueError, find_substr_pos, '"a"', 1)
