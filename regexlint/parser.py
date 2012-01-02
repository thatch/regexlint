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

import sys
import weakref

from pygments.lexer import RegexLexer, include, using, bygroups
from pygments.token import Other


# Special types, others are used in the parser below in normal Pygments
# manner.

PROGRESSION = Other.Progression
ALTERNATION = Other.Alternation
REPETITON = Other.Repetition
CHARRANGE = Other.CharRange

class Node(object):
    def __init__(self, t, start=None, data=None):
        self.type = t
        self.data = data # type-dependent
        self.children = [] # type-dependent

        self.start = start
        self.end = None
        self._parent = None
        self._next = None

    def add_child(self, obj):
        obj._parent = weakref.ref(self)
        if self.children:
            self.children[-1]._next = weakref.ref(obj)
        self.children.append(obj)

    def close(self, pos, data):
        self.end = pos + len(data)

    def next(self):
        if self.children:
            return self.children[0]
        else:
            return self.next_no_children()

    def next_no_children(self):
        if self._next:
            return self._next()
        p = self._parent
        while p:
            if p()._next:
                return p()._next()
            p = p()._parent

    def parent(self):
        if self._parent:
            return self._parent()

    def is_descentant_of(self, other):
        if self is other:
            return True
        p = self._parent
        while p:
            if p() is other:
                return True
            p = p()._parent

    def __repr__(self):
        return '<%s type=%r data=%r %r>' % (self.__class__.__name__,
                                            self.type, self.data, self.children)

    def __eq__(self, obj):
        return (self.type == obj.type and self.data == obj.data and
                self.children == obj.children and self.start == obj.start and
                self.end == obj.end)

class CharRange(object):
    def __init__(self, a, b):
        self.a = a
        self.b = b

    def __repr__(self):
        return '<%s %r-%r>' % (self.__class__.__name__, self.a, self.b)

class CharClass(Node):
    def __init__(self, t, start=None):
        super(CharClass, self).__init__(t, start)
        self.negated = False

    def close(self, pos, data):
        super(CharClass, self).close(pos, data)

        n = []
        it = iter(self.children)
        for child in it:
            c = child.data
            if not n and c == '^':
                # caret is special only when the first char
                self.negated = True
            elif c == '-':
                # dash is special only when not the first or last char.
                is_range = bool(n)
                if is_range:
                    try:
                        next_child = it.next()
                    except StopIteration:
                        is_range = False
                if is_range:
                    n.append(CharRange(n.pop(), next_child))
                else:
                    n.append(child)
            else:
                n.append(child)

        self.chars = n

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
            (r'\(\?=', Other.Open.Lookahead),
            (r'\(\?!', Other.Open.NegativeLookahead),
            (r'\(\?<!', Other.Open.NegativeLookbehind),
            (r'\(\?<', Other.Open.Lookbehind),
            (r'(\(\?P=)(\w+)(\))', Other.Open.ExistsNamed),
            (r'\(\?\(\d+\)', Other.Open.Exists),
            (r'\(\?#.*?\)', Other.Comment),
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
            (r'\\.', Other.Suspicious),
            (r'[\-^]', Other.Special),
            include('simpleliteral'),
        ],
        'meta': [
            (r'\.', Other.Dot),
            (r'\\\^', Other.Anchor.Beginning),
            (r'\\\$', Other.Anchor.End),
            (r'\\b', Other.Anchor.WordBoundary),
            (r'\\A', Other.Anchor.BeginningOfString),
            (r'\\Z', Other.Anchor.EndOfString),
            (r'\*\?', Other.Repetition.NongreedyStar),
            (r'\*', Other.Repetition.Star),
            (r'\+\?', Other.Repetition.NongreedyPlus),
            (r'\+', Other.Repetition.Plus),
            (r'\?\?', Other.Repetition.NongreedyQuestion),
            (r'\?', Other.Repetition.Question),
            (r'\{\d+,(?:\d+)?\}', Other.Repetition.Curly),
            (r'\{,\d+\}', Other.Repetition.Curly),

        ],
        'simpleliteral': [
            (r'[^\\^-]', Other.Literal),
            (r'\0[0-7]{0,3}', Other.Literal.Oct), # \0 is legal
            (r'\\x[0-9a-fA-F]{2}', Other.Literal.Hex),
            (r'\\[\[\]]', Other.Literal.Bracket),
            (r'\\[()]', Other.Literal.Paren),
            (r'\\n', Other.Newline),
            (r'\\\.', Other.Literal.Dot),
            (r'\\\\', Other.Literal.Backslash),
            (r'\\\*', Other.Literal.Star),
            (r'\\\+', Other.Literal.Plus),
            (r'\\\|', Other.Literal.Alternation),
            (r'\\\'', Other.Suspicious.Squo),
            (r'\\\"', Other.Suspicious.Dquo),
            (r'\\[sSwW]', Other.BuiltinCharclass),
            (r'\\.', Other.Suspicious),
        ],
    }

    @classmethod
    def get_parse_tree(cls, s):
        n = Node(t=PROGRESSION, data='', start=0)
        n.raw = s
        open_stack = [n]

        for i, ttype, data in cls().get_tokens_unprocessed(s):
            if ttype in Other.Open:
                # stack depth ++
                n = Node(t=ttype, start=i, data=data)
                open_stack.append(n)
            elif ttype is Other.CharClass:
                n = CharClass(t=ttype, start=i)
                open_stack.append(n)
            elif ttype in (Other.CloseParen, Other.CloseCharClass):
                # stack depth -- or -= 2
                if open_stack[-2].type is ALTERNATION:
                    open_stack[-1].close(i, '')
                    open_stack[-2].add_child(open_stack[-1])
                    open_stack.pop()
                    open_stack[-1].close(i, '')
                    open_stack[-2].add_child(open_stack[-1])
                    open_stack.pop()
                assert (open_stack[-1].type in Other.Open or
                        open_stack[-1].type in Other.CharClass)
                open_stack[-1].close(i, data)
                open_stack[-2].add_child(open_stack[-1])
                open_stack.pop()
            elif ttype is Other.Alternate:
                # stack depth same, or +=2
                if len(open_stack) < 2 or open_stack[-2].type is not ALTERNATION:
                    # Create new alternation, push 2
                    start = open_stack[-1].start + len(open_stack[-1].data)
                    n = Node(t=ALTERNATION, start=start)
                    p = Node(t=PROGRESSION, start=start)
                    for c in open_stack[-1].children:
                        p.add_child(c) # sets parent
                    del open_stack[-1].children[:]
                    open_stack.append(n)
                    p.close(i, "")
                    n.add_child(p)
                    p2 = Node(t=PROGRESSION, start=i+len(data))
                    open_stack.append(p2)
                else:
                    # close & swap, replicating close a bit
                    open_stack[-1].close(i, "") # progression
                    open_stack[-2].add_child(open_stack[-1])
                    open_stack[-1] = Node(t=PROGRESSION, start=i+len(data))
            elif ttype in Other.Repetition:
                c = open_stack[-1].children.pop()
                n = Node(t=REPETITON, data=data, start=c.start)
                n.add_child(c)
                n.close(i, data)
                open_stack[-1].add_child(n)
            else:
                # stack depth same
                n = Node(t=ttype, data=data, start=i)
                open_stack[-1].add_child(n)

        # don't pop here
        if len(open_stack) == 3 and open_stack[-2].type is ALTERNATION:
            open_stack[-1].close(len(s), '')
            open_stack[-2].add_child(open_stack[-1])
            open_stack[-2].close(len(s), '')
            open_stack[-3].add_child(open_stack[-2])
            open_stack.pop()
            open_stack.pop()

        open_stack[0].close(len(s), '')
        assert len(open_stack) == 1
        return open_stack[0]

def charclass(c):
    if 'A' <= c <= 'Z':
        return 'upper'
    elif 'a' <= c <= 'z':
        return 'lower'
    else:
        return 'other'

def fmttree(t):
    if not hasattr(t, 'children') or not t.children:
        return [repr(t)]

    r = []
    r.append('<%s type=%r data=%r>' % (t.__class__.__name__, t.type, t.data))
    for c in t.children:
        r.extend('  ' + f for f in fmttree(c))
    return r

def width(tok):
    """Returns whether the given token type might consume characters."""
    if (tok in (Other.Directive,
                Other.Open.Lookahead, Other.Open.NegativeLookahead,
                Other.Open.NegativeLookbehind, Other.Open.Lookbehind,
                Other.Comment) or (tok in Other.Anchor)):
        return False
    else:
        return True

def main(args):
    if not args:
        regex = r'(foo|bar)|[ba]z'
    else:
        regex = args[0]

    r = Regex()
    #for x in r.get_tokens_unprocessed(regex):
    #    print x

    tree = r.get_parse_tree(regex)
    print '\n'.join(fmttree(tree))

if __name__ == '__main__':
    main(sys.argv[1:])
