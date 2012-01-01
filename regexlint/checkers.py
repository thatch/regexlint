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

import logging
from regexlint.parser import *

# no nulls in regex (per docs)
# no funny literals (use \xnn)
# charclass range only on alpha
# no empty alternation
# no alternation with out of order prefix

def _has_end_anchor(reg):
    if not isinstance(reg, Node):
        return False

    return any(_has_end_anchor(s) for s in reg.alternations)


def check_no_nulls(reg, errs):
    num = '101'
    level = logging.ERROR
    msg = 'Null characters not allowed (python docs)'
    pos = reg.raw.find('\x00')
    if pos != -1:
        errs.append((num, level, pos, msg))

def check_no_newlines(reg, errs):
    num = '102'
    level = logging.ERROR
    msg = 'Newline characters not allowed (java compat, use a rawstring)'

    # Ignore re.VERBOSE modes for now.  I'm not sure how they fit in with
    # Java.
    directives = list(find_all_by_type(reg, Other.Directive))
    if directives and any('x' in d.data for d in directives):
        return

    pos = reg.raw.find('\n')
    if pos != -1:
        errs.append((num, level, pos, msg))

def check_no_empty_alternations(reg, errs):
    num = '103'
    level = logging.ERROR
    msg = 'Empty string allowed in alternation starting at position %d, use *'
    for n in find_all_by_type(reg, Other.Progression):
        if (not n.children and n._parent and
            n._parent().type is Other.Alternation):
            errs.append((num, level, n.start or 0, msg % (n.start or 0)))

def check_charclass_homogeneous_ranges(reg, errs):
    num = '104'
    level = logging.ERROR
    msg = 'Range in character class is not homogeneous near position %d'
    for c in all_charclass(reg):
        for p in c.chars:
            if isinstance(p, CharRange):
                if p.a[0] in Other.Literal and p.b[0] in Other.Literal:
                    # should be single character data, can compare
                    assert len(p.a[1] == 1)
                    assert len(p.b[1] == 1)
                    if charclass(p.a[1]) != charclass(p.b[1]):
                        errs.append((num, level, 0, msg % c.start))
                    # only positive ranges are allowed.
                    if ord(p.a[1]) >= ord(p.b[1]):
                        errs.append((num, level, 0, 'order %d' % c.start))
                elif p.a[0] not in Other.Literal and p.b[0] not in Other.Literal:
                    # punctuation range?
                    errs.append((num, level, 0, msg % c.start))
                else:
                    # strange range.
                    errs.append((num, level, 0, msg % c.start))

def check_prefix_ordering(reg, errs):
    """
    Checks for things of the form a|ab, which should be ab|a due to python
    quirks.
    """
    num = '105'
    level = logging.ERROR
    msg = 'Potential out of order alternation between %r and %r'
    for n in find_all_by_type(reg, Other.Alternation):
        # TODO: check whether successors have width()
        prev = None
        for i in n.children:
            assert i.type is Other.Progression
            #print i, reg.raw[n.start:n.end]
            if not all(x.type in Other.Literal or
                       x.type in Other.Literals or
                       x.type in Other.Newline or
                       x.type in Other.Suspicious
                       for x in i.children):
                #print "Can't check", i
                return
            t = ''.join(x.data for x in i.children)
            #print "Check", repr(t), repr(prev)
            if prev is not None and t.startswith(prev):
                errs.append((num, level, n.start, msg % (prev, t)))
                break
            prev = t

def check_no_python_named_capture_groups(reg, errs):
    num = '106'
    level = logging.ERROR
    msg = 'Python named capture group'
    for n in all_nodes(reg):
        if n.type in Other.Open.NamedCapturing:
            errs.append((num, level, n.start, msg))
            break

def manual_toknum(reg, errs, desired_number):
    num = '107'
    level = logging.ERROR
    msg = 'Wrong number of groups(%d) for bygroups(%d)'
    n = len(list(find_all_by_type(reg, Other.Open.Capturing)))
    if n != desired_number:
        errs.append((num, level, 0, msg % (n, desired_number)))


def get_alternation_possibilities(alt):
    """
    alt is the 2d list, i.e. [['a'], ['a', 'b']]
    """
    for i in alt:
        for j in _alternation_helper(i):
            yield j

def _alternation_helper(i):
    if not i:
        yield ''
        return

    if isinstance(i[0], Node):
        # BAH
        raise NotImplementedError("Can't handle alternations with Nodes")
    elif isinstance(i[0], CharRange):
        # BAH
        raise NotImplementedError("Can't handle alternations with CharRange")
    else:
        # a literal, I hope!
        for j in _alternation_helper(i[1:]):
            yield i[0][1] + j


def all_charclass(regex_root):
    s = [regex_root]
    while s:
        i = s.pop(0)
        assert isinstance(i, Node)
        for alt in i.alternations:
            for x in alt:
                if isinstance(x[1], Node):
                    s.append(x[1])
                elif isinstance(x[1], CharRange):
                    yield x[1]

def find_all(regex_root):
    regex = regex_root
    while regex:
        yield regex
        regex = regex.next()

def find_all_by_type(regex_root, t):
    for regex in find_all(regex_root):
        if regex.type == t:
            yield regex

def run_all_checkers(regex):
    errs = []
    for k, f in globals().iteritems():
        if k.startswith('check_'):
            #print 'running', k
            try:
                f(regex, errs)
            except Exception, e:
                errs.append(('999', logging.ERROR, 0, "Checker %s encountered error parsing: %s" % (f, repr(e))))
    return errs

if __name__ == '__main__':
    print run_all_checkers(Regex().get_parse_tree(r'(foo|) [a-Mq-&]'))
