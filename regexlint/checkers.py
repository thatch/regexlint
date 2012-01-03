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
import logging
from regexlint.parser import *
from regexlint.util import *


def check_no_nulls(reg, errs):
    num = '101'
    level = logging.ERROR
    msg = 'Null characters not allowed (python docs)'
    pos = reg.raw.find('\x00')
    if pos != -1:
        errs.append((num, level, pos, msg))

def check_no_bels(reg, errs):
    num = '110'
    level = logging.ERROR
    msg = 'You probably don\'t want a bell. Use another backslash, raw string, or use \\x08 instead)'
    pos = reg.raw.find('\b')
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
    msg = 'Empty string allowed in alternation starting at position %d, use ?'
    for n in find_all_by_type(reg, Other.Progression):
        if (not n.children and n.parent() and
            n.parent().type is Other.Alternation):
            errs.append((num, level, n.start or 0, msg % (n.start or 0)))

def check_charclass_homogeneous_ranges(reg, errs):
    num = '104'
    level = logging.ERROR
    msg = 'Range in character class is not homogeneous near position %d'
    msg2 = 'Range in character class goes backwards near position %d'
    for c in find_all_by_type(reg, Other.CharClass):
        for p in c.chars:
            if isinstance(p, CharRange):
                if p.a.type is Other.Literal and p.b.type is Other.Literal:
                    # should be single character data, can compare
                    assert len(p.a.data) == 1
                    assert len(p.b.data) == 1
                    if charclass(p.a.data) != charclass(p.b.data):
                        errs.append((num, level, p.a.start, msg % p.a.start))
                    # only positive ranges are allowed.
                    if ord(p.a.data) >= ord(p.b.data):
                        errs.append((num, level, p.a.start, msg2 % p.a.start))
                elif p.a.type not in Other.Literal and p.b.type not in Other.Literal:
                    # punctuation range?
                    errs.append((num, level, p.a.start, msg % p.a.start))
                else:
                    # strange range.
                    errs.append((num, level, p.a.start, msg % p.a.start))

def check_prefix_ordering(reg, errs):
    """
    Checks for things of the form a|ab, which should be ab|a due to python
    quirks.
    """
    num = '105'
    level = logging.ERROR
    msg = 'Potential out of order alternation between %r and %r'
    for n in find_all_by_type(reg, Other.Alternation):
        run_checks = True
        for i in between(n, None):
            # TODO this heuristic is easy to game
            if i.type in Other.Anchor or i.type in Other.Open or width(i.type):
                run_checks = False
                break
        if not run_checks:
            continue

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
                errs.append((num, level, i.start, msg % (prev, t)))
                break
            prev = t

def check_no_python_named_capture_groups(reg, errs):
    num = '106'
    level = logging.ERROR
    msg = 'Python named capture group'
    for n in find_all_by_type(reg, Other.Open.NamedCapturing):
        errs.append((num, level, n.start, msg))
        break

def bygroups_check_toknum(reg, errs, desired_number):
    num = '107'
    level = logging.ERROR
    msg = 'Wrong number of groups(%d) for bygroups(%d)'
    n = len(list(find_all_by_type(reg, Other.Open.Capturing)))
    if n < desired_number:
        errs.append((num, level, 0, msg % (n, desired_number)))
    elif n > desired_number:
        errs.append((num, logging.INFO, 0,
                     (msg % (n, desired_number)) + ' (extra groups)'))

def bygroups_check_overlap(reg, errs, desired_number):
    num = '108'
    level = logging.ERROR
    msg = 'Nested/gapped capture groups but using bygroups'
    n = list(find_all_by_type(reg, Other.Open.Capturing))
    if not n:
        # manual_toknum should already complain about this case.
        return
    # Ignore re.VERBOSE modes for now.
    directives = list(find_all_by_type(reg, Other.Directive))
    if directives and any('x' in d.data for d in directives):
        return
    # The order returned by find_all_by_type need not be the same as python's
    # group numbers, in the case of nesting.
    prev_end = 0
    prev = None
    #print reg.raw, desired_number
    for idx, group in enumerate(n):
        if group.parent().type in Other.Repetition:
            group = group.parent()
        #print "Loop", i, group, group.start, group.end

        if group.start > prev_end:
            #print "Have prev"
            # This code allows a parent to be ok'd, and all children to be
            # ignored (without having to change between()'s code)
            j = find_bad_between(prev, group, has_width)
            if j:
                errs.append((num, level, j.start, msg))
        elif group.start < prev_end:
            if idx >= desired_number:
                # This case is uninteresting -- bygroups ignores extra groups,
                # so it's possible to nest within the last group.
                errs.append((num, logging.INFO, group.start, msg + ' (extra groups)'))
                group = prev
            else:
                #print "Boring", group.start, prev_end
                errs.append((num, level, group.start, msg))
                group = prev

        prev_end = group.end
        prev = group

    if prev_end != reg.end:
        #print "End check", prev
        # This code allows a parent to be ok'd, and all children to be
        # ignored (without having to change between()'s code)
        j = find_bad_between(prev, None, has_width)
        if j:
            errs.append((num, level, j.start, msg))

def bygroups_check_no_capture_group_in_repetition(reg, errs, desired_number):
    num = '109'
    level = logging.ERROR
    msg = 'Capture group should not be within a repetition'
    for idx, capture in enumerate(find_all_by_type(reg, Other.Open.Capturing)):
        parent = capture.parent()
        while parent:
            # Question works in Pygments at the moment, but is subject to change.
            if (parent.type in Other.Repetition and
                parent.type is not Other.Repetition.Question):
                if idx >= desired_number:
                    errs.append((num, logging.INFO, capture.start, msg + ' (extra groups)'))
                else:
                    errs.append((num, level, capture.start, msg))
            parent = parent.parent()


def run_all_checkers(regex, expected_groups=None):
    errs = []
    for k, f in globals().iteritems():
        if k.startswith('check_'):
            #print 'running', k
            try:
                f(regex, errs)
            except Exception, e:
                errs.append(('999', logging.ERROR, 0, "Checker %s encountered error parsing: %s" % (f, repr(e))))
        elif k.startswith('bygroups_check_') and expected_groups:
            try:
                f(regex, errs, expected_groups)
            except Exception, e:
                errs.append(('999', logging.ERROR, 0, "Checker %s encountered error parsing: %s" % (f, repr(e))))
    return errs

def main(args):
    if not args:
        regex = r'(foo|) [a-Mq-&]'
    else:
        regex = args[0]
    print run_all_checkers(Regex().get_parse_tree(regex))

if __name__ == '__main__':
    main(sys.argv[1:])
