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

import re
import sys
import logging

from pygments.token import Token

from regexlint.parser import *
from regexlint.util import *
from regexlint.charclass import *


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
    msg = 'You probably don\'t want a backspace. Use another backslash, raw string, or use \\x08 instead)'
    pos = reg.raw.find('\b')
    if pos != -1:
        errs.append((num, level, pos, msg))

def check_no_newlines(reg, errs):
    num = '102'
    level = logging.ERROR
    msg = 'Newline characters not allowed (java compat, use a rawstring)'

    # Ignore re.VERBOSE modes for now.  I'm not sure how they fit in with
    # Java.
    if reg.effective_flags & re.VERBOSE:
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
                if (p.a.type is Other.Literal.Hex and
                    p.b.type is Other.Literal.Hex):
                    pass # hex notation for both sides ok to skip this check
                elif p.a.type is Other.Literal and p.b.type is Other.Literal:
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
                elif (p.a.type in (Other.Literal.Unicode,
                                   Other.Literal.LongUnicode) and
                      p.b.type in (Other.Literal.Unicode,
                                   Other.Literal.LongUnicode)):
                    pass # ok
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

def bygroups_check_toknum(reg, errs, desired_groups):
    num = '107'
    level = logging.ERROR
    msg = 'Wrong number of groups(%d) for bygroups(%d)'
    n = len(list(find_all_by_type(reg, Other.Open.Capturing)))
    desired_number = len(desired_groups)
    if n < desired_number:
        errs.append((num, level, 0, msg % (n, desired_number)))
    elif n > desired_number:
        # If there are nested groups anywhere but the last, check_overlap will
        # find them.  This checker doesn't look at start/stop positions.
        errs.append((num, logging.INFO, 0,
                     (msg % (n, desired_number)) + ' (extra groups)'))

def bygroups_check_overlap(reg, errs, desired_groups):
    num = '108'
    level = logging.ERROR
    msg = 'Nested capture group other than the final one using bygroups'
    msg2 = 'Gap in capture groups using bygroups'
    n = list(find_all_by_type(reg, Other.Open.Capturing))
    if not n:
        # bygroups_check_toknum should already complain about this case.
        return
    desired_number = len(desired_groups)
    # The order returned by find_all_by_type appears to be the same as python's
    # group numbers (matters most when nesting).
    prev_end = 0
    prev = None
    #print reg.raw, desired_number
    for idx, group in enumerate(n):
        if group.parent().type in Other.Repetition:
            group = group.parent()
        #print "Loop", i, group, group.start, group.end

        if group.parsed_start > prev_end:
            #print "Have prev"
            # This code allows a parent to be ok'd, and all children to be
            # ignored (without having to change between()'s code)
            j = find_bad_between(prev, group, has_width)
            if j:
                errs.append((num, level, j.start, msg2))
        elif group.parsed_start < prev_end:
            if idx >= desired_number:
                # This case is uninteresting -- bygroups ignores extra groups,
                # so it's possible to nest within the last group.
                errs.append((num, logging.INFO, group.start,
                             msg + ' (extra groups)'))
                group = prev
            else:
                # This is a nested group with the outer one prior to the last
                # one bygroups cares about
                #print "Boring", group.start, prev_end
                if desired_groups[idx] is not None:
                    errs.append((num, level, group.start, msg))
                group = prev

        prev_end = group.parsed_end
        prev = group

    if prev_end != reg.parsed_end:
        #print "End check", prev
        # This code allows a parent to be ok'd, and all children to be
        # ignored (without having to change between()'s code)
        j = find_bad_between(prev, None, has_width)
        if j:
            errs.append((num, level, j.start, msg))

def bygroups_check_no_capture_group_in_repetition(reg, errs, desired_groups):
    num = '109'
    level = logging.ERROR
    msg = 'Capture group should not be within a repetition when using bygroups'
    desired_number = len(desired_groups)
    for idx, capture in enumerate(find_all_by_type(reg, Other.Open.Capturing)):
        parent = capture.parent()
        while parent:
            # Question works in Pygments at the moment, but is subject to change.
            if (parent.type in Other.Repetition and
                parent.type is not Other.Repetition.Question):
                if idx >= desired_number:
                    errs.append((num, logging.INFO, capture.start, msg + ' (extra groups)'))
                elif desired_groups[idx] is not None:
                    errs.append((num, level, capture.start, msg))
            parent = parent.parent()


def check_no_consecutive_dots(reg, errs):
    num = '111'
    level = logging.WARNING
    msg = 'Consecutive dots, use .{2} if this is intentional'
    for x in find_all_by_type(reg, Other.Dot):
        n = x.next_no_children()
        if n and n.type is Other.Dot:
            errs.append((num, level, x.start, msg))
            break

def check_unicode_escapes(reg, errs):
    num = '112'
    level = logging.ERROR
    msg = 'Regex parser does not handle unicode, use u"" (not ur""!) string or escape backslash if intentional'
    r_unicode = re.compile(r'(?<!\\)(\\[uU][0-9a-fA-F]|\\N{)')
    for m in r_unicode.finditer(reg.raw):
        errs.append((num, level, m.start(), msg))

def check_bad_flags(reg, errs):
    num = '113'
    level = logging.WARNING
    msg = 'Manually set flag %r, but do not need it'

    directives = list(find_all_by_type(reg, Other.Directive))
    # TODO flag the correct directive
    flags = ''.join(d.data for d in directives)
    if not flags:
        return

    if 'x' in flags:
        # In order for x to matter, there must exist a node that has start !=
        # parsed_start.  The easiest place to find this is on the last one, since
        # both values should be nondecreasing.
        if reg.children[-1].parsed_end == len(reg.raw):
            errs.append((num, level, directives[0].start, msg % 'x'))

        # TODO See if there's bare whitespace
        pass

    if 'i' in flags:
        # See if there are a-zA-Z
        try:
            for char in find_all_by_type(reg, Other.Literal):
                if 'a' <= char.data <= 'z' or 'A' <= char.data <= 'Z':
                    raise Break()

            # This part only checks ranges, because the single characters were
            # already checked directly above.
            import string
            alpha = set(map(ord, string.ascii_letters))
            for cc in find_all_by_type(reg, Other.CharClass):
                for char in cc.chars:
                    if isinstance(char, CharRange):
                        this_range = set(range(char.codepoint_a, char.codepoint_b))
                        if this_range & alpha:
                            raise Break()
        except Break:
            pass
        else:
            errs.append((num, level, directives[0].start, msg % 'i'))

    if 's' in flags:
        # See if there are any dots.
        dots = list(find_all_by_type(reg, Other.Dot))
        if not dots:
            errs.append((num, level, directives[0].start, msg % 's'))

    if 'm' in flags:
        # Only ^$ differ in this mode.
        anchors = list(find_all_by_type(reg, (Other.Anchor.Beginning, Other.Anchor.End)))
        if not anchors:
            errs.append((num, level, directives[0].start, msg % 'm'))


def check_suspicious_anchors(reg, errs):
    num = '114'
    level = logging.WARNING
    msg = 'Suspicious use of anchors in alternation'

    for rep in find_all_by_type(reg, Other.Alternation):
        first = rep
        while first.children:
            first = first.children[0]

        last = rep
        while last.children:
            last = last.children[-1]

        if first.type in Other.Anchor and last.type in Other.Anchor:
            errs.append((num, level, first.start, msg))


def check_single_character_classes(reg, errs):
    num = '115'
    level = logging.INFO # harmless, for now
    msg = 'Only a single character in character class'

    for cc in find_all_by_type(reg, Other.CharClass):
        if (len(cc.chars) == 1 and
            not cc.negated and
            cc.parent().type not in Other.Repetition and
            (not isinstance(cc.chars[0], CharRange) or
             cc.chars[0].codepoint_a == cc.chars[0].codepoint_b)):
            errs.append((num, level, cc.start, msg))


def check_charclass_overlap(reg, errs):
    num = '117'
    level = logging.WARNING
    msg = 'Overlap in character class: %r'

    for cc in find_all_by_type(reg, Other.CharClass):
        if len(set(cc.matching_character_codes)) != len(cc.matching_character_codes):
            counts = {}
            for i in cc.matching_character_codes:
                counts.setdefault(i, 0)
                counts[i] += 1
            dupes = [chr(k) for k, v in counts.items() if v > 1]
            errs.append((num, level, cc.start, msg % (dupes,)))

def check_charclass_case_insensitive_overlap(reg, errs):
    num = '122'
    level = logging.WARNING
    msg = 'Overlap due to case insensitive mode'

    if not reg.effective_flags & re.IGNORECASE:
        return

    def fold(i):
        if i >= 97 and i <= 122:
            return i - 32
        return i

    # TODO: This only finds the most obvious ones, like
    # (?i)[0-9a-fA-F], and doesn't do anything about non-ranges.
    for cc in find_all_by_type(reg, Other.CharClass):
        ranges = set()
        for c in cc.chars:
            if isinstance(c, CharRange):
                a = eval_char(c.a.data)
                b = eval_char(c.b.data)
                if (fold(a), fold(b)) in ranges:
                    errs.append((num, level, c.a.start, msg))
                ranges.add((fold(a), fold(b)))

COMMON_SINGLE_CHAR_CODES = list(map(ord, '()*+. '))

def check_charclass_len(reg, errs):
    num = '118'
    level = logging.WARNING
    msg = 'Superfluous character class when only one char'

    for cc in find_all_by_type(reg, Other.CharClass):
        if not cc.negated and len(cc.matching_character_codes) == 1:
            # Some people use [*] instead of \* -- allow this for now as an INFO
            if (cc.matching_character_codes[0] in COMMON_SINGLE_CHAR_CODES
                or cc.parent().type in Other.Repetition):
                errs.append((num, logging.INFO, cc.start, msg))
            elif (reg.flags & re.VERBOSE and
                  cc.matching_character_codes[0] == ord('#')):
                errs.append((num, logging.WARNING, cc.start,
                             msg + ': use backslash'))
            else:
                errs.append((num, level, cc.start, msg))


def check_charclass_negation(reg, errs):
    num = '119'
    level = logging.WARNING
    msg = 'Instead of negating character class, flip case of builtin class'

    for cc in find_all_by_type(reg, Other.CharClass):
        if (cc.negated and len(cc.children) == 2 and
            cc.children[1].type in Other.BuiltinCharclass):
            errs.append((num, level, cc.start, msg))


def check_multiline_anchors(reg, errs):
    num = '120'
    level = logging.WARNING
    msg = 'Use of ^ or $ without multiline mode: use \\A or \\Z explicitly.'

    if reg.effective_flags & re.M:
        return

    for anchor in find_all_by_type(reg, (Other.Anchor.Beginning,
                                         Other.Anchor.End)):
        errs.append((num, level, anchor.start, msg))


def check_wide_unicode(reg, errs):
    num = '121'
    level = logging.WARNING
    msg = 'Wide unicode causes problems in narrow builds'

    if isinstance(reg.raw, type(u'')):
        for lit in find_all_by_type(reg, Other.Literal):
            if len(lit.data) == 1 and ord(lit.data) > 65535:
                # entire codepoint, we're in a wide build
                if isinstance(lit.parent(), CharClass) or lit.parent().type in Other.Repetition:
                    errs.append((num, level, lit.start, msg))
                    break
            elif (len(lit.data) == 1 and 0xd800 <= ord(lit.data) <= 0xdbff and
                  isinstance(lit.parent(), CharClass)):
                # high surrogate byte, we're in a narrow build, does the wrong thing
                n = lit.next_no_children()
                if (n is not None and n.type is Other.Literal and len(n.data) == 1 and
                    0xdc00 <= ord(n.data) <= 0xdfff):
                    errs.append((num, level, lit.start, msg))
                    break
            elif (len(lit.data) == 1 and 0xdc00 <= ord(lit.data) <= 0xdfff and
                  lit.parent().type in Other.Repetition):
                # low surrogate byte, imagine HH LL +
                errs.append((num, level, lit.start, msg))
                break
            # TODO figure out if there's a way to catch overly-verbose unicode
            # (needs to happen before string parsing)
            # TODO expand to more use of suspicious unicode


def check_charclass_simplify(reg, errs):
    num = '123'
    level = logging.WARNING
    msg = 'Regex can be written more simply: %s -> %s'

    if any(ord(c) > 255 for c in reg.raw):
        # Many of the operations performed here assume 8-bit ascii.
        return

    for c in find_all_by_type(reg, Other.CharClass):
        existing_score = charclass_score(c)
        try:
            new_codes, negated = simplify_charclass(c.matching_character_codes,
                                                    reg.effective_flags & re.I)
        except WontOptimize:
            continue
        new_score = charclass_score(new_codes, negated)
        if new_score < existing_score:
            if len(new_codes) == 1 and not negated and isinstance(new_codes[0], int):
                new_class = esc(chr(new_codes[0]))
            elif len(new_codes) == 1 and not negated and isinstance(new_codes[0], str):
                new_class = new_codes[0]
            else:
                new_class = '[%s%s]' % (negated and '^' or '',
                                        build_output(new_codes))

            errs.append((num, level, c.start,
                         msg % (c.reconstruct(), new_class)))


def check_unescaped_braces(reg, errs):
    num = '124'
    level = logging.ERROR
    msg = 'Curly braces should be escaped if not repeat spec (regex compat)'

    for brace in find_all_by_type(reg, Other.UnescapedCurly):
        errs.append((num, level, brace.start, msg))


def check_redundant_repetition(reg, errs):
    num = '125'
    level = logging.WARNING
    msg = 'Redundant repetition spec: %s'

    for repeat in find_all_by_type(reg, Other.Repetition.Curly):
        if repeat.min == 1 and repeat.max == 1:
            errs.append((num, level, repeat.start, (msg % repeat.end_data) +
                        ' can be omitted'))
        elif repeat.min == repeat.max and ',' in repeat.end_data:
            errs.append((num, level, repeat.start, msg % repeat.end_data))
        elif repeat.min == 0 and repeat.max is None and '*' not in repeat.end_data:
            errs.append((num, level, repeat.start, 'should be *'))
        elif repeat.min == 1 and repeat.max is None and '+' not in repeat.end_data:
            errs.append((num, level, repeat.start, 'should be +'))
        elif (repeat.min == 0 and repeat.max == 1 and not
              repeat.end_data.startswith('?')):
            errs.append((num, level, repeat.start, 'should be +'))



def manual_check_for_empty_string_match(reg, errs, raw_pat):
    # Note: callback functions get a pass here, since they're used for
    # indentation tracking in SassLexer (and friends).
    # Explicitly, '#pop' and 'next-state' ARE checked because if they
    # intentionally match on empty string, they should be using default().
    if isinstance(raw_pat[1], Token.__class__):
        regex = re.compile(raw_pat[0])
        # Either match on empty string, or empty string at the end of a word
        if regex.match('') or regex.match('a', 1):
            errs.append(('999', logging.ERROR, 0, 'Matches empty string'))
        #remove_error(errs, '103')


def run_all_checkers(regex, expected_groups=None):
    errs = []
    for k, f in globals().items():
        if k.startswith('check_'):
            #print 'running', k, regex
            try:
                f(regex, errs)
            except Exception as e:
                errs.append(('999', logging.ERROR, 0, "Checker %s encountered error parsing: %s" % (f, repr(e))))
        elif k.startswith('bygroups_check_') and expected_groups:
            try:
                f(regex, errs, expected_groups)
            except Exception as e:
                errs.append(('999', logging.ERROR, 0, "Checker %s encountered error parsing: %s" % (f, repr(e))))
    return errs

def main(args):
    if not args:
        regex = r'(foo|) [a-Mq-&]'
    else:
        regex = args[0]
    for num, severity, pos1, text in run_all_checkers(Regex.get_parse_tree(regex)):
        print('%s%s:%s:%s' %
              (logging.getLevelName(severity)[0], num, pos1, text))

if __name__ == '__main__':
    main(sys.argv[1:])
