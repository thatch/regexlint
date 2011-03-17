"""
This script is several layered hacks to be able to point out clang-style errors
for a specific line of Python code (likely in a string literal).  Do not take
as an example of well-written Python.
"""
import re

from pygments.lexers.agile import PythonLexer
from pygments.token import Punctuation, Name, Text, String

def point_out_error(mod, path_to_str, pos):
    pass


R_CLASSEXTRACT = re.compile(r'class (\w+).*:\n([\w\W]*?)(?=^class|\Z)', re.MULTILINE)

open_braces = '[{('
close_braces = ']})'


def find_offending_line(mod, clsname, state, idx, pos):
    """
    Returns a tuple of (lineno, charpos_start, charpos_end, line_content)
    """
    if '\n' in mod:
        mod_text = mod
    else:
        if mod.endswith('.pyc') or mod.endswith('.pyo'):
            mod = mod[:-1]
        with file(mod, 'r') as f:
            mod_text = f.read()

    # skip as far as possible using regular expressions, then start lexing.
    for m in R_CLASSEXTRACT.finditer(mod_text):
        #print "Got class", m.group(1), '...' + repr(m.group(0)[-40:])
        if m.group(1) == clsname: break
    else:
        return None
        #raise ValueError("Can't find class %r" % (clsname,))

    def match_brace(brace):
        target = close_braces[open_braces.index(brace)]
        #print "matching brace", brace, target, it
        for x in it:
            #print x
            if x[-2] in Punctuation and x[-1] == target:
                #print "  found"
                return True
            elif x[-2] in Punctuation and x[-1] in open_braces:
                # begin again!
                if not match_brace(x[-1]):
                    #print "  fail2"
                    return False
        #print "  inner fail"
        return False

    def until(t):
        #print "until", t
        for x in it:
            if t == x[-1]:
                #print "  found", repr(x[-1])
                return
        
    level = 0
    tuple_idx = 0
    string_pos = 0

    def amal(i):
        si = None
        pt = None
        pd = None
        for idx, tok, data in i:
            if tok in String: tok = String
            if tok == pt == String:
                pd += data
            else:
                if pt:
                    yield si, pt, pd
                pt = tok
                pd = data
                si = idx
        if pt:
            yield si, pt, pd

    def filt(i):
        line = 1 + mod_text[:m.start()].count('\n')
        col = 0
        for _, b, c in i:
            #print "got", b, repr(c)
            yield line, col, b, c
            line += c.count('\n')
            if '\n' in c:
                col = len(c) - c.index('\n') - 1 # TODO unsure of this number.
            else:
                col += len(c)

    it = filt(amal(PythonLexer().get_tokens_unprocessed(m.group(0))))

    for x, y, ttyp, text in it:
        #print "Loop", level, ttyp, repr(text)
        if level == 0 and ttyp is Name:
            if text == 'tokens':
                until('=')
                until('{')
                level = 1
        elif level == 1 and ttyp in String:
            #print "key", text
            key = eval(text, {}, {})
            if key != state:
                until('[')
                match_brace('[')
            else:
                level = 2
        elif level == 2:
            if text == '(':
                # open a tuple
                level = 3
            elif text == ')':
                level = 1 # honestly this should be able to just return
                #print "too late", idx, tuple_idx
                return
        elif level == 3:
            #print "  idx", tuple_idx
            if text == ')':
                level = 2
                tuple_idx += 1
            elif text == '(':
                match_brace('(')
            elif tuple_idx == idx and ttyp in String:
                # this might be it!
                s = eval(text, {}, {})
                #print "maybe", string_pos, pos, (string_pos+len(s))
                if string_pos <= pos < (string_pos+len(s)):
                    # need to point in here
                    (dx, d1, d2) = find_substr_pos(text, pos - string_pos)
                    if dx == 0:
                        d1 += y
                        d2 += y
                    return (x+dx, d1, d2, mod_text.splitlines()[x+dx-1])
                else:
                    string_pos += len(s)
            elif tuple_idx == idx and ttyp in Name:
                # If they're concatenating strings with vars, ignore.
                break

strp = {
    '': re.compile(r'\\(?:[\\abfnrtv"\']|\n|x[a-fA-F0-9]{2}|[0-7]{1,3})|'
                   r'[\w\W]'),
    'u': re.compile(r'\\(?:[\\abfnrtv"\']|\n|N{.*?}|u[a-fA-F0-9]{4}|'
                    r'U[a-fA-F0-9]{8}|x[a-fA-F0-9]{2}|[0-7]{1,3})|[\w\W]'),
    'r': re.compile(r'\\\\|[\w\W]'),
    'ur': re.compile(r'\\(?:\\|u[a-fA-F0-9]{4}|U[a-fA-F0-9]{8})|[\w\W]'),
}

def rindex(a, x):
    for i in range(len(a)-1, -1, -1):
        if a[i] == x:
            return i
    raise ValueError("Not found")

def find_substr_pos(s, target):
    if s[-3:] in ('"""', "'''"):
        end_quote = s[-3:]
    else:
        end_quote = s[-1]
    p = s.find(end_quote)
    mods = s[:p]
    body = s[p+len(end_quote):-len(end_quote)]

    chars = strp[mods].findall(body)

    if target >= len(chars) or target < 0:
        raise ValueError("Impossible, out of bounds")

    l = 0
    q = p+len(end_quote)+sum(map(len, chars[:target]))

    # only for triplequoted strings
    if '\n' in chars[:target]:
        print "GOT", target, chars[:target]
        l = chars[:target].count('\n')
        _ = rindex(chars[:target], '\n') + 1
        print "_", _
        q = sum(map(len, chars[_:target]))
        print "q", l, q, q+len(chars[target])

    print q
    return (l, q, q+len(chars[target]))


def mark(lineno, d1, d2, text):
    print "  " + text
    print "  " + " " * d1 + '^' * (d2-d1) + ' ' + 'here'
