# Copyright 2011-2014 Google Inc.
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

import re
import sre_parse
import sys
import weakref

from regexlint.util import *

from pygments.lexer import RegexLexer, include, using, bygroups, default
from pygments.token import Other


WHITESPACE = ' \t\n\r\f\v'
DIGITS = '0123456789'
WORD = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ' + DIGITS + '_'

# Special types, others are used in the parser below in normal Pygments
# manner.

PROGRESSION = Other.Progression
ALTERNATION = Other.Alternation

class Node(object):
    def __init__(self, t, start=None, parsed_start=None, data=None):
        self.type = t
        self.data = data # type-dependent
        self.end_data = ''
        self.children = [] # type-dependent

        self.start = start
        self.parsed_start = parsed_start
        # This clause is necessary for simple tokens that don't have children
        # -- they need to essentially be autoclosed, here.
        if start is not None and parsed_start is not None and data is not None:
            self.end = start + len(data)
            self.parsed_end = parsed_start + len(data)
        else:
            self.end = None
            self.parsed_end = None
        self._parent = None
        self._next = None

    def add_child(self, obj):
        obj._parent = weakref.ref(self)
        if self.children:
            self.children[-1]._next = weakref.ref(obj)
        self.children.append(obj)

    def close(self, pos, parsed_pos, data):
        self.end = pos + len(data)
        self.parsed_end = parsed_pos + len(data)
        self.end_data = data

    def next(self):
        if self.children:
            return self.children[0]
        else:
            return self.next_no_children()

    def next_no_children(self):
        # pylint: disable-msg=E1102
        if self._next:
            return self._next()
        p = self._parent
        while p:
            if p()._next:
                return p()._next()
            p = p()._parent
        # pylint: enable-msg=E1102

    def parent(self):
        if self._parent:
            return self._parent()  # pylint: disable-msg=E1102

    def is_descentant_of(self, other):
        # pylint: disable-msg=E1102
        if self is other:
            return True
        p = self._parent
        while p:
            if p() is other:
                return True
            p = p()._parent
        # pylint: enable-msg=E1102

    def reconstruct(self):
        """Return the regex string for this branch of the tree."""
        r = []
        # Special case for repetition
        if self.data and self.data != self.end_data:
            r.append(self.data)
        for i, c in enumerate(self.children):
            r.append(c.reconstruct())
            if self.type is ALTERNATION and i < len(self.children) - 1:
                r.append('|')
        r.append(self.end_data)
        return ''.join(r)

    def __repr__(self):
        return '<%s type=%r data=%r start=%r end=%r %r>' % (
            self.__class__.__name__, self.type, self.data, self.start,
            self.end, self.children)

    def __eq__(self, obj):
        return (self.type == obj.type and self.data == obj.data and
                self.children == obj.children and self.start == obj.start and
                self.end == obj.end)


class RootNode(Node):
    def __init__(self, t, start=None, parsed_start=None, data=None, raw=None,
                 flags=None, effective_flags=None):
        super(RootNode, self).__init__(t, start, parsed_start, data)
        self.raw = raw
        self.flags = flags
        self.effective_flags = effective_flags


class CharRange(object):
    def __init__(self, a, b):
        self.a = a
        self.b = b
        self.codepoint_a = eval_char(a.data)
        self.codepoint_b = eval_char(b.data)

    def __repr__(self):
        return '<%s %r-%r>' % (self.__class__.__name__, self.a, self.b)


class CharClass(Node):
    def __init__(self, t, start=None, parsed_start=None):
        super(CharClass, self).__init__(t, start, parsed_start)
        self.negated = False
        self.chars = None
        self.matching_character_codes = None

    def close(self, pos, parsed_pos, data):
        super(CharClass, self).close(pos, parsed_pos, data)

        n = []
        it = iter(self.children)
        for child in it:
            c = child.data
            if not n and c == '^':
                # caret is special only when the first char
                self.negated = True
            elif c == '-':
                # dash is special only when it's the first char or directly
                # follows another range (say, [0-9-x]).
                next_child = None
                if n and not isinstance(n[-1], CharRange):
                    try:
                        next_child = next(it)
                    except StopIteration:
                        next_child = None
                if next_child:
                    n.append(CharRange(n.pop(), next_child))
                else:
                    n.append(child)
            else:
                n.append(child)

        # One of the checkers may care about order, so don't set-ify yet
        self.matching_character_codes = []
        for i in n:
            if isinstance(i, CharRange):
                self.matching_character_codes.extend(
                    range(eval_char(i.a.data), eval_char(i.b.data)+1))
            elif i.data == r'\s':
                self.matching_character_codes.extend(map(ord, WHITESPACE))
            elif i.data == r'\w':
                self.matching_character_codes.extend(map(ord, WORD))
            elif i.data == r'\d':
                self.matching_character_codes.extend(map(ord, DIGITS))
            elif i.data == r'\S':
                whitespace = set(map(ord, WHITESPACE))
                self.matching_character_codes.extend(i for i in range(256) if i
                                                     not in whitespace)
            elif i.data == r'\W':
                word = set(map(ord, WORD))
                self.matching_character_codes.extend(i for i in range(256) if i
                                                     not in word)
            elif i.data == r'\D':
                digits = set(map(ord, DIGITS))
                self.matching_character_codes.extend(i for i in range(256) if i
                                                     not in digits)
            else:
                self.matching_character_codes.append(eval_char(i.data))

        if self.negated:
            # destroys order :(
            self.matching_character_codes = \
                    list(set(range(256)) - set(self.matching_character_codes))
        self.chars = n

    def reconstruct(self):
        return '[%s%s]' % ('^' if self.negated else '',
                           ''.join((x.a.data + '-' + x.b.data) if
                            isinstance(x, CharRange) else x.data
                            for x in self.chars))

class Repetition(Node):
    def __init__(self, t, start=None, parsed_start=None, data=None):
        super(Repetition, self).__init__(t, start, parsed_start, data)
        self.min = None
        self.max = None
        self.greedy = None

    def close(self, pos, parsed_pos, data):
        super(Repetition, self).close(pos, parsed_pos, data)

        if '*' in self.end_data:
            self.min, self.max = (0, None)
        elif '+' in self.end_data:
            self.min, self.max = (1, None)
        elif self.end_data[0] == '?':
            self.min, self.max = (0, 1)
        else:
            t = self.end_data.strip('{}?') # strip curlies
            if ',' in t:
                a, b = t.split(',')
                if a:
                    self.min = int(a)
                else:
                    self.min = 0
                if b:
                    self.max = int(b)
                else:
                    self.max = None
            else:
                self.min, self.max = (int(t), int(t))

        self.greedy = not (self.end_data.endswith('?') and self.end_data != '?')


class VerboseRegexTryAgain(Exception): pass


class BaseRegex(object):

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
            (r'(\(\?P=)(\w+)(?=\))', Other.Open.ExistsNamed),
            (r'\(\?\(\d+\)', Other.Open.Exists),
            (r'\(\?#.*?\)', Other.Comment),
            (r'\(', Other.Open.Capturing),
            (r'\)', Other.CloseParen),
            (r'\[', Other.CharClass, 'charclass_start'),
            (r'\\[1-9][0-9]?', Other.Backref),
            include('only_in_verbose'),
            include('suspicious'),
            include('meta'),
            (r'[{}]', Other.UnescapedCurly),  # legal in sre, illegal in regex
            include('simpleliteral'),
            (r'[^\\()|\[\]]+', Other.Literals), # TODO
        ],
        'suspicious': [
            # misdone backreferences, tabs, newlines, and bel
            (r'[\x00-\x08\x0a\x0d]', Other.Suspicious),
        ],
        'charclass_start': [
            (r'\^', Other.NegateCharclass, 'charclass_squarebracket_special'),
            default('charclass_squarebracket_special'),
        ],
        'charclass_squarebracket_special': [
            (r'\]', Other.Literal.CloseCharClass, 'charclass_rest'),
            default('charclass_rest'),
        ],
        'charclass_rest': [
            (r'\]', Other.CloseCharClass, '#pop:3'),
            (r'\\-', Other.EscapedDash),
            (r'[\-^]', Other.Special),
            include('simpleliteral'),
            (r'\\.', Other.Suspicious),
        ],
        'meta': [
            (r'\.', Other.Dot),
            (r'\^', Other.Anchor.Beginning),
            (r'\$', Other.Anchor.End),
            (r'\\b', Other.Anchor.WordBoundary),
            (r'\\A', Other.Anchor.BeginningOfString),
            (r'\\Z', Other.Anchor.EndOfString),
            (r'\*\?', Other.Repetition.NongreedyStar),
            (r'\*', Other.Repetition.Star),
            (r'\+\?', Other.Repetition.NongreedyPlus),
            (r'\+', Other.Repetition.Plus),
            (r'\?\?', Other.Repetition.NongreedyQuestion),
            (r'\?', Other.Repetition.Question),
            (r'\{\d+,(?:\d+)?\}\??', Other.Repetition.Curly),
            (r'\{,?\d+\}\??', Other.Repetition.Curly),
        ],
        'simpleliteral': [
            (r'[^\\^-]', Other.Literal),
            (r'\\0[0-7]{0,3}', Other.Literal.Oct), # \0 is legal
            (r'\\x[0-9a-fA-F]{2}', Other.Literal.Hex),
            (r'\\[\[\]]', Other.Literal.Bracket),
            (r'\\[()]', Other.Literal.Paren),
            (r'\\t', Other.Tab),
            (r'\\n', Other.Newline),
            (r'\\\.', Other.Literal.Dot),
            (r'\\\\', Other.Literal.Backslash),
            (r'\\\*', Other.Literal.Star),
            (r'\\\+', Other.Literal.Plus),
            (r'\\\|', Other.Literal.Alternation),
            (r'\\\^', Other.Literal.Caret),
            (r'\\\$', Other.Literal.Dollar),
            (r'\\\?', Other.Literal.Question),
            (r'\\[{}]', Other.Literal.Curly),
            (r'\\\'', Other.Suspicious.Squo),
            (r'\\\"', Other.Suspicious.Dquo),
            (r'\\[sSwWdD]', Other.BuiltinCharclass),
            (r'\\.', Other.Suspicious), # Other unnecessary escapes
        ],
        'only_in_verbose': [],
    }

    @classmethod
    def get_parse_tree(cls, s, flags=0):
        effective_flags = sre_parse.parse(s, flags).pattern.flags

        if effective_flags & re.VERBOSE:
            return VerboseRegex._get_parse_tree(s, flags, effective_flags)
        return cls._get_parse_tree(s, flags, effective_flags)

    @classmethod
    def _get_parse_tree(cls, s, flags, effective_flags):
        n = RootNode(t=PROGRESSION, data='', start=0, parsed_start=0, raw=s,
                     flags=flags, effective_flags=effective_flags)
        verbose = effective_flags & re.VERBOSE

        open_stack = [n]
        verbose_offset = 0
        #print "Using class", cls, cls.tokens['only_in_verbose']

        # these two need default values because normally they would be set in
        # the last iteration of the loop, but this doesn't happen for empty
        # string.
        j = 0
        data = ''

        # i, j are the raw position and parsed position, respectively.
        for i, ttype, data in cls().get_tokens_unprocessed(s):  # pylint: disable-msg=E1101
            #print i, ttype, data
            if not data: continue  # HACK for '' match for [][]

            if not verbose and ttype in Other.Directive and 'x' in data:
                raise VerboseRegexTryAgain()

            if ttype in Other.Verbose:
                #print "Found verbose token"
                verbose_offset += len(data)
                continue
            else:
                j = i - verbose_offset

            if ttype in Other.Open:
                # stack depth ++
                n = Node(t=ttype, start=i, parsed_start=j, data=data)
                open_stack.append(n)
            elif ttype is Other.CharClass and open_stack[-1].type is not Other.CharClass:
                n = CharClass(t=ttype, start=i, parsed_start=j)
                open_stack.append(n)
            elif ttype in (Other.CloseParen, Other.CloseCharClass):
                # stack depth -- or -= 2
                if open_stack[-2].type is ALTERNATION:
                    open_stack[-1].close(i, j, '')
                    open_stack[-2].add_child(open_stack[-1])
                    open_stack.pop()
                    open_stack[-1].close(i, j, '')
                    open_stack[-2].add_child(open_stack[-1])
                    open_stack.pop()
                assert (open_stack[-1].type in Other.Open or
                        open_stack[-1].type in Other.CharClass)
                open_stack[-1].close(i, j, data)
                open_stack[-2].add_child(open_stack[-1])
                open_stack.pop()
            elif ttype is Other.Alternate:
                # stack depth same, or +=2
                if len(open_stack) < 2 or open_stack[-2].type is not ALTERNATION:
                    # Create new alternation, push 2
                    #print s, open_stack[-1]
                    start = open_stack[-1].start + len(open_stack[-1].data)
                    parsed_start = open_stack[-1].parsed_start + len(open_stack[-1].data)
                    n = Node(t=ALTERNATION, start=start, parsed_start=parsed_start)
                    p = Node(t=PROGRESSION, start=start, parsed_start=parsed_start)
                    for c in open_stack[-1].children:
                        p.add_child(c) # sets parent
                    del open_stack[-1].children[:]
                    open_stack.append(n)
                    p.close(i, j, "")
                    n.add_child(p)
                    p2 = Node(t=PROGRESSION, start=i+len(data), parsed_start=j+len(data))
                    open_stack.append(p2)
                else:
                    # close & swap, replicating close a bit
                    open_stack[-1].close(i, j, "") # progression
                    open_stack[-2].add_child(open_stack[-1])
                    open_stack[-1] = Node(t=PROGRESSION, start=i+len(data),
                                          parsed_start=j+len(data))
            elif ttype in Other.Repetition:
                c = open_stack[-1].children.pop()
                n = Repetition(t=ttype, data='', start=c.start,
                               parsed_start=c.parsed_start)
                n.add_child(c)
                n.close(i, j, data)
                open_stack[-1].add_child(n)
            else:
                # stack depth same
                n = Node(t=ttype, data=data, start=i, parsed_start=j)
                open_stack[-1].add_child(n)

        # don't pop here
        if len(open_stack) == 3 and open_stack[-2].type is ALTERNATION:
            # TODO len(data) might fail if the regex is empty string, so
            # default above...
            open_stack[-1].close(len(s), j+len(data), '')
            open_stack[-2].add_child(open_stack[-1])
            open_stack[-2].close(len(s), j+len(data), '')
            open_stack[-3].add_child(open_stack[-2])
            open_stack.pop()
            open_stack.pop()

        open_stack[0].close(len(s), j+len(data), '')
        assert len(open_stack) == 1, s + repr(open_stack)
        return open_stack[0]


class Regex(BaseRegex, RegexLexer):
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


class VerboseRegex(BaseRegex, RegexLexer):
    name = 'verbose_regex'
    mimetypes = ['text/x-verbose-regex']
    filenames = ['*.regex'] # fake
    flags = 0 # not multiline

    tokens = dict(BaseRegex.tokens)
    tokens['only_in_verbose'] = [
        (r'\s+', Other.Verbose.Whitespace),
        (r'#.*', Other.Verbose.Comment),
    ]


def parser_main(args):
    if not args:
        regex = r'(foo|bar)|[ba]z'
    else:
        regex = args[0]

    r = Regex()
    #for x in r.get_tokens_unprocessed(regex):
    #    print x

    tree = r.get_parse_tree(regex)
    print('\n'.join(fmttree(tree)))

if __name__ == '__main__':
    parser_main(sys.argv[1:])
