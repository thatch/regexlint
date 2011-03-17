import sys

from pygments.lexer import RegexLexer, include, using, bygroups
from pygments.token import Other

class Node(object):
    def __init__(self, t, start=None):
        self.type = t 
        self.alternations = []
        self.start = start
        self.end = None

    def add_token(self, ttyp, data):
        if not self.alternations:
            self.alternations.append([])
        if ttyp is Other.Alternate:
            self.alternations.append([])
        else:
            self.alternations[-1].append((ttyp, data))

    def close(self, pos, ttyp, data):
        self.end = pos + len(data)
        return True

    def __repr__(self):
        return '<%s %r>' % (self.type, self.alternations)

class CharRange(object):
    def __init__(self, a, b):
        self.a = a
        self.b = b

class CharClass(object):
    def __init__(self, start=None):
        self.negated = False
        self.chars = []
        self.type = Other.CharClass
        self.start = start
        self.end = None

    def add_token(self, ttyp, data):
        #if not self and data == '^':
        #    self.negated = True
        #else:
        self.chars.append((ttyp, data))

    def close(self, pos, ttyp, data):
        n = []
        it = iter(self.chars)
        for t, c in it:
            if not n and data == '^':
                # caret is special only when the first char
                self.negated = True
            elif n and data == '-':
                # dash is special only when not the first or last char.
                try:
                    nt, nc = it.next()
                except StopIteration:
                    n.append((t, c))
                else:
                    n.append(CharRange(n.pop(), nt, nc))

        self.chars = n
        self.end = pos + len(data)

    def __repr__(self):
        return '<CharClass %r>' % (self.chars,)

class Regex(RegexLexer):
    r"""
    This is a RegexLexer that parses python regex syntax.  The included helper
    functions will turn its token stream into a psuedo-syntax-tree.  The goal
    is to recognize strange, error-prone regex constructs and provide warnings
    to users.  Examples of the sort of error-prone things:

    bad     good
    [][] = [\[\]]
    [A-z] = [\x41-\x7a] or [A-Za-z]
    '\n' = r'\n' or '\\n'

    Just because I wrote a parser in Pygments doesn't mean that it's generally
    a good idea.  Remember that.  This started because I need to run a regex
    lint against the Python strings, before the regex simplifier gets its hands
    on it.  This is fairly close to the best possible, but doesn't catch a few
    things (mainly in non-raw strings).
    """
    name = 'regex'
    mimetypes = ['text/x-regex']
    filenames = ['*.regex'] # fake
    flags = 0 # not multiline

    tokens = {
        'root': [
            (r'\|', Other.Alternate),
            (r'\(\?[iLmsux]+\)', Other.Directive),
            (r'\(\?:', Other.Open.NonCapturing),
            (r'(\(\?P<)(.*?)(>)', Other.Open.NamedCapturing),
            # TODO (?P=name) backref
            # TODO (?#...) comment
            (r'\(', Other.Open.Capturing),
            (r'\)', Other.CloseParen),
            (r'\[', Other.CharClass, 'charclass'),
            # TODO backreferences
            include('suspicious'),
            include('meta'),
            include('simpleliteral'),
            (r'[^\\()|\[\]]+', Other.Literals), # TODO
        ],
        'suspicious': [
            # misdone backreferences, tabs, newlines, and bel
            (r'[\x00-\x08\x0a\x0d]', Other.Suspicious),
        ],
        'charclass': [
            # TODO parse [][]
            (r'\]', Other.CloseCharClass, '#pop'),
            (r'\\-', Other.EscapedDash),
            include('simpleliteral'),
        ],
        'meta': [
            (r'\.', Other.Dot),
            (r'\^', Other.Beginning),
            (r'\$', Other.End),
            (r'\\b', Other.WordBoundary),
            (r'\*\?', Other.NongreedyStar),
            (r'\*', Other.Star),
            (r'\+\?', Other.NongreedyPlus),
            (r'\+', Other.Plus),
            (r'\?\?', Other.NongreedyQuestion),
            (r'\?', Other.Question),

        ],
        'simpleliteral': [
            (r'[^\\^-]', Other.Literal),
            (r'\0[0-7]{0,3}', Other.OctLiteral), # \0 is legal
            (r'\\x[0-9a-fA-F]{2}', Other.HexLiteral),
            (r'\\[\[\]]', Other.LiteralBracket),
            (r'\\[()]', Other.LiteralParen),
            (r'\\n', Other.Newline),
            (r'\\\\', Other.LiteralBackslash),
            (r'\\\|', Other.LiteralAlternation),
        ],
    }

    @classmethod
    def get_parse_tree(cls, s):
        open_stack = [Node(None)]
        open_stack[0].raw = s
        open_stack[0].start = 0

        for i, ttype, data in cls().get_tokens_unprocessed(s):
            if ttype in Other.Open:
                open_stack.append(Node(ttype, i)) # TODO store name of named group
            elif ttype is Other.CharClass:
                open_stack.append(CharClass(i))
            elif ttype in (Other.CloseParen, Other.CloseCharClass):
                open_stack[-1].close(i, ttype, data)
                open_stack[-2].add_token(open_stack[-1].type, open_stack[-1])
                open_stack.pop()
            else:
                open_stack[-1].add_token(ttype, data)

        open_stack[0].close(len(s), None, '')
        return open_stack[0]

def charclass(c):
    if 'A' <= c <= 'Z':
        return 'upper'
    elif 'a' <= c <= 'z':
        return 'lower'
    else:
        return 'other'

def main(args):
    r = Regex()
    for x in r.get_tokens_unprocessed(r"a(b|c[de])" + '\b'):
        print x

    print repr(r.get_parse_tree(r'(foo|bar|[ba]z)'))

if __name__ == '__main__':
    main(sys.argv)
