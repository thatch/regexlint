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

import logging
import re
import sys

from pygments.token import Other, Token

from regexlint.charclass import (
    WontOptimize,
    build_output,
    charclass_score,
    simplify_charclass,
)
from regexlint.parser import CharRange, Regex
from regexlint.util import (
    Break,
    between,
    charclass,
    esc,
    eval_char,
    find_all_by_type,
    find_bad_between,
    has_width,
    width,
)


def check_no_bels(reg, errs):
    num = "110"
    level = logging.ERROR
    msg = "You probably don't want a backspace. Use another backslash, raw string, or use \\x08 instead)"
    pos = reg.raw.find("\b")
    if pos != -1:
        errs.append((num, level, pos, msg))


def check_no_empty_alternations(reg, errs):
    num = "103"
    level = logging.ERROR
    msg = "Empty string allowed in alternation starting at position %d, use ?"
    for n in find_all_by_type(reg, Other.Progression):
        if not n.children and n.parent() and n.parent().type is Other.Alternation:
            errs.append((num, level, n.start or 0, msg % (n.start or 0)))


def check_charclass_homogeneous_ranges(reg, errs):
    num = "104"
    level = logging.ERROR
    msg = "Range in character class is not homogeneous near position %d"
    msg2 = "Range in character class goes backwards near position %d"
    for c in find_all_by_type(reg, Other.CharClass):
        for p in c.chars:
            if isinstance(p, CharRange):
                if p.a.type is Other.Literal.Hex and p.b.type is Other.Literal.Hex:
                    pass  # hex notation for both sides ok to skip this check
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
                elif p.a.type in (
                    Other.Literal.Unicode,
                    Other.Literal.LongUnicode,
                ) and p.b.type in (Other.Literal.Unicode, Other.Literal.LongUnicode):
                    pass  # ok
                else:
                    # strange range.
                    errs.append((num, level, p.a.start, msg % p.a.start))


def check_prefix_ordering(reg, errs):
    """
    Checks for things of the form a|ab, which should be ab|a due to python
    quirks.
    """
    num = "105"
    level = logging.ERROR
    msg = "Potential out of order alternation between %r and %r"
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
            # print i, reg.raw[n.start:n.end]
            if not all(
                x.type in Other.Literal
                or x.type in Other.Literals
                or x.type in Other.Newline
                or x.type in Other.Suspicious
                for x in i.children
            ):
                # print "Can't check", i
                return
            t = "".join(x.data for x in i.children)
            # print "Check", repr(t), repr(prev)
            if prev is not None and t.startswith(prev):
                errs.append((num, level, i.start, msg % (prev, t)))
                break
            prev = t


def bygroups_check_no_python_named_capture_groups(reg, errs, desired_groups):
    num = "106"
    level = logging.ERROR
    msg = "Python named capture group used with bygroups()"

    for n in find_all_by_type(reg, Other.Open.NamedCapturing):
        errs.append((num, level, n.start, msg))
        break


def bygroups_check_toknum(reg, errs, desired_groups):
    num = "107"
    level = logging.ERROR
    msg = "Wrong number of groups(%d) for bygroups(%d)"
    n = len(list(find_all_by_type(reg, Other.Open.Capturing)))
    desired_number = len(desired_groups)
    if n < desired_number:
        errs.append((num, level, 0, msg % (n, desired_number)))
    elif n > desired_number:
        # If there are nested groups anywhere but the last, check_overlap will
        # find them.  This checker doesn't look at start/stop positions.
        errs.append(
            (num, logging.INFO, 0, (msg % (n, desired_number)) + " (extra groups)")
        )


def bygroups_check_overlap(reg, errs, desired_groups):
    num = "108"
    level = logging.ERROR
    msg = "Nested capture group other than the final one using bygroups"
    msg2 = "Gap in capture groups using bygroups"
    n = list(find_all_by_type(reg, Other.Open.Capturing))
    if not n:
        # bygroups_check_toknum should already complain about this case.
        return
    desired_number = len(desired_groups)
    # The order returned by find_all_by_type appears to be the same as python's
    # group numbers (matters most when nesting).
    prev_end = 0
    prev = None
    # print reg.raw, desired_number
    for idx, group in enumerate(n):
        if group.parent().type in Other.Repetition:
            group = group.parent()
        # print "Loop", i, group, group.start, group.end

        if group.parsed_start > prev_end:
            # print "Have prev"
            # This code allows a parent to be ok'd, and all children to be
            # ignored (without having to change between()'s code)
            j = find_bad_between(prev, group, has_width)
            if j:
                errs.append((num, level, j.start, msg2))
        elif group.parsed_start < prev_end:
            if idx >= desired_number:
                # This case is uninteresting -- bygroups ignores extra groups,
                # so it's possible to nest within the last group.
                errs.append((num, logging.INFO, group.start, msg + " (extra groups)"))
                group = prev
            else:
                # This is a nested group with the outer one prior to the last
                # one bygroups cares about
                # print "Boring", group.start, prev_end
                if desired_groups[idx] is not None:
                    errs.append((num, level, group.start, msg))
                group = prev

        prev_end = group.parsed_end
        prev = group

    if prev_end != reg.parsed_end:
        # print "End check", prev
        # This code allows a parent to be ok'd, and all children to be
        # ignored (without having to change between()'s code)
        j = find_bad_between(prev, None, has_width)
        if j:
            errs.append((num, level, j.start, msg2))


def bygroups_check_no_capture_group_in_repetition(reg, errs, desired_groups):
    num = "109"
    level = logging.ERROR
    msg = "Capture group should not be within a repetition when using bygroups"
    desired_number = len(desired_groups)
    for idx, capture in enumerate(find_all_by_type(reg, Other.Open.Capturing)):
        parent = capture.parent()
        while parent:
            # Question works in Pygments at the moment, but is subject to change.
            if (
                parent.type in Other.Repetition
                and parent.type is not Other.Repetition.Question
            ):
                if idx >= desired_number:
                    errs.append(
                        (num, logging.INFO, capture.start, msg + " (extra groups)")
                    )
                elif desired_groups[idx] is not None:
                    errs.append((num, level, capture.start, msg))
            parent = parent.parent()


def check_no_consecutive_dots(reg, errs):
    num = "111"
    level = logging.WARNING
    msg = "Consecutive dots, use .{2} if this is intentional"
    for x in find_all_by_type(reg, Other.Dot):
        n = x.next_no_children()
        if n and n.type is Other.Dot:
            errs.append((num, level, x.start, msg))
            break


def check_bad_flags(reg, errs):
    num = "113"
    level = logging.WARNING
    msg = "Manually set flag %r, but do not need it"

    directives = list(find_all_by_type(reg, Other.Directive))
    # TODO flag the correct directive
    flags = "".join(d.data for d in directives)
    if not flags:
        return

    if "x" in flags:
        # In order for x to matter, there must exist a node that has start !=
        # parsed_start.  The easiest place to find this is on the last one, since
        # both values should be nondecreasing.
        if reg.children[-1].parsed_end == len(reg.raw):
            errs.append((num, level, directives[0].start, msg % "x"))

        # TODO See if there's bare whitespace
        pass

    if "i" in flags:
        # See if there are a-zA-Z
        try:
            for char in find_all_by_type(reg, Other.Literal):
                if "a" <= char.data <= "z" or "A" <= char.data <= "Z":
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
            errs.append((num, level, directives[0].start, msg % "i"))

    if "s" in flags:
        # See if there are any dots.
        dots = list(find_all_by_type(reg, Other.Dot))
        if not dots:
            errs.append((num, level, directives[0].start, msg % "s"))

    if "m" in flags:
        # Only ^$ differ in this mode.
        anchors = list(
            find_all_by_type(reg, (Other.Anchor.Beginning, Other.Anchor.End))
        )
        if not anchors:
            errs.append((num, level, directives[0].start, msg % "m"))


def check_suspicious_anchors(reg, errs):
    num = "114"
    level = logging.WARNING
    msg = "Suspicious use of anchors in alternation"

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
    num = "115"
    level = logging.INFO  # harmless, for now
    msg = "Only a single character in character class"

    for cc in find_all_by_type(reg, Other.CharClass):
        if (
            len(cc.chars) == 1
            and not cc.negated
            and cc.parent().type not in Other.Repetition
            and (
                not isinstance(cc.chars[0], CharRange)
                or cc.chars[0].codepoint_a == cc.chars[0].codepoint_b
            )
        ):
            errs.append((num, level, cc.start, msg))


def check_charclass_overlap(reg, errs):
    num = "117"
    level = logging.WARNING
    msg = "Overlap in character class: %r"

    for cc in find_all_by_type(reg, Other.CharClass):
        if len(set(cc.matching_character_codes)) != len(cc.matching_character_codes):
            counts = {}
            for i in cc.matching_character_codes:
                counts.setdefault(i, 0)
                counts[i] += 1
            dupes = [chr(k) for k, v in counts.items() if v > 1]
            errs.append((num, level, cc.start, msg % (dupes,)))


def check_charclass_case_insensitive_overlap(reg, errs):
    num = "122"
    level = logging.WARNING
    msg = "Overlap due to case insensitive mode"

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


COMMON_SINGLE_CHAR_CODES = list(map(ord, "()*+. "))


def check_charclass_len(reg, errs):
    num = "118"
    level = logging.WARNING
    msg = "Superfluous character class when only one char"

    for cc in find_all_by_type(reg, Other.CharClass):
        if not cc.negated and len(cc.matching_character_codes) == 1:
            # Some people use [*] instead of \* -- allow this for now as an INFO
            if (
                cc.matching_character_codes[0] in COMMON_SINGLE_CHAR_CODES
                or cc.parent().type in Other.Repetition
            ):
                errs.append((num, logging.INFO, cc.start, msg))
            elif reg.flags & re.VERBOSE and cc.matching_character_codes[0] == ord("#"):
                errs.append((num, logging.WARNING, cc.start, msg + ": use backslash"))
            else:
                errs.append((num, level, cc.start, msg))


def check_charclass_negation(reg, errs):
    num = "119"
    level = logging.WARNING
    msg = "Instead of negating character class, flip case of builtin class"

    for cc in find_all_by_type(reg, Other.CharClass):
        if (
            cc.negated
            and len(cc.children) == 2
            and cc.children[1].type in Other.BuiltinCharclass
        ):
            errs.append((num, level, cc.start, msg))


def check_multiline_anchors(reg, errs):
    num = "120"
    level = logging.WARNING
    msg = "Use of ^ or $ without multiline mode: use \\A or \\Z explicitly."

    if reg.effective_flags & re.M:
        return

    for anchor in find_all_by_type(reg, (Other.Anchor.Beginning, Other.Anchor.End)):
        errs.append((num, level, anchor.start, msg))


def check_charclass_simplify(reg, errs):
    num = "123"
    level = logging.WARNING
    msg = "Regex can be written more simply: %s -> %s"

    if any(ord(c) > 255 for c in reg.raw) or reg.effective_flags & re.UNICODE:
        # Many of the operations performed here assume 8-bit ascii.
        return

    for c in find_all_by_type(reg, Other.CharClass):
        existing_score = charclass_score(c)
        try:
            new_codes, negated = simplify_charclass(
                c.matching_character_codes, reg.effective_flags & re.I
            )
        except WontOptimize:
            continue
        new_score = charclass_score(new_codes, negated)
        if new_score < existing_score:
            if len(new_codes) == 1 and not negated and isinstance(new_codes[0], int):
                new_class = esc(chr(new_codes[0]))
            elif len(new_codes) == 1 and not negated and isinstance(new_codes[0], str):
                new_class = new_codes[0]
            else:
                new_class = "[%s%s]" % (negated and "^" or "", build_output(new_codes))

            errs.append((num, level, c.start, msg % (c.reconstruct(), new_class)))


def check_unescaped_braces(reg, errs):
    num = "124"
    level = logging.ERROR
    msg = "Curly braces should be escaped if not repeat spec (regex compat)"

    for brace in find_all_by_type(reg, Other.UnescapedCurly):
        errs.append((num, level, brace.start, msg))


def check_redundant_repetition(reg, errs):
    num = "125"
    level = logging.WARNING
    msg = "Redundant repetition spec: %s"

    for repeat in find_all_by_type(reg, Other.Repetition.Curly):
        if repeat.min == 1 and repeat.max == 1:
            errs.append(
                (num, level, repeat.start, (msg % repeat.end_data) + " can be omitted")
            )
        elif repeat.min == repeat.max and "," in repeat.end_data:
            errs.append((num, level, repeat.start, msg % repeat.end_data))
        elif repeat.min == 0 and repeat.max is None and "*" not in repeat.end_data:
            errs.append((num, level, repeat.start, "should be *"))
        elif repeat.min == 1 and repeat.max is None and "+" not in repeat.end_data:
            errs.append((num, level, repeat.start, "should be +"))
        elif (
            repeat.min == 0 and repeat.max == 1 and not repeat.end_data.startswith("?")
        ):
            errs.append((num, level, repeat.start, "should be +"))


def _whitespace_atom(branch):
    """Return the single atom of an alternation branch when it matches only
    whitespace that ``\\s`` already covers (unwrapping a repetition such as
    ``\\s+``), else None.
    """
    if len(branch.children) != 1:
        return None
    atom = branch.children[0]
    if atom.type in Other.Repetition and len(atom.children) == 1:
        atom = atom.children[0]
    if (
        (atom.type is Other.BuiltinCharclass and atom.data == "\\s")
        or atom.type in (Other.Newline, Other.Tab)
        or (atom.type is Other.Suspicious and atom.data == "\\r")
        or (atom.type is Other.Literal and atom.data in " \t\n\r\x0b\x0c")
    ):
        return atom
    return None


def check_redundant_whitespace_alternation(reg, errs):
    # https://github.com/pygments/pygments/pull/3186
    num = "126"
    level = logging.WARNING
    msg = "Redundant whitespace alternation, simplify to \\s+ (\\s already matches \\n)"

    outer = (
        Other.Repetition.Plus,
        Other.Repetition.NongreedyPlus,
        Other.Repetition.Star,
        Other.Repetition.NongreedyStar,
    )
    for rep in find_all_by_type(reg, Other.Repetition):
        if rep.type not in outer or len(rep.children) != 1:
            continue
        group = rep.children[0]
        if group.type not in Other.Open or len(group.children) != 1:
            continue
        alt = group.children[0]
        if alt.type is not Other.Alternation:
            continue
        # Every branch must be \s-subsumed whitespace, and at least one must be
        # \s itself (which is what makes the other branches redundant).
        has_s = False
        for branch in alt.children:
            atom = _whitespace_atom(branch)
            if atom is None:
                break
            if atom.type is Other.BuiltinCharclass:
                has_s = True
        else:
            if has_s:
                errs.append((num, level, rep.start or 0, msg))


def check_dot_newline_alternation(reg, errs):
    # https://github.com/pygments/pygments/pull/3187
    num = "127"
    level = logging.WARNING
    msg = "Alternation matching any character, simplify to [\\s\\S]"

    # (.|\n) matches every character, since . matches all but \n. It is the
    # [\s\S] idiom spelled as a per-character alternation; matching a single
    # character class is markedly faster: ~4x on a long comment body, ~13%
    # end-to-end on comment-heavy sources (pygments PR #3187).
    allowed = {Other.Dot, Other.Newline, Other.Tab, Other.Suspicious}
    for alt in find_all_by_type(reg, Other.Alternation):
        atoms = [b.children[0] for b in alt.children if len(b.children) == 1]
        if len(atoms) != len(alt.children):
            continue
        types = {a.type for a in atoms}
        if Other.Dot in types and Other.Newline in types and types <= allowed:
            errs.append((num, level, alt.start or 0, msg))


def check_redundant_lookaround(reg, errs):
    # https://github.com/pygments/pygments/pull/3192
    num = "128"
    level = logging.WARNING

    negative = (Other.Open.NegativeLookahead, Other.Open.NegativeLookbehind)
    lookarounds = (Other.Open.Lookahead, Other.Open.Lookbehind) + negative
    for node in find_all_by_type(reg, Other.Open):
        if node.type not in lookarounds:
            continue
        body = node.children
        # (?<=...) lexes its leading '=' as a literal child; drop it.
        if node.type is Other.Open.Lookbehind:
            body = body[1:]
        if len(body) != 1 or body[0].type not in Other.Anchor:
            continue
        # A lookaround wrapping a single zero-width assertion is just the
        # assertion (or its negation). Only \b has a named negation, \B.
        if node.type in negative:
            if body[0].type is Other.Anchor.WordBoundary:
                errs.append(
                    (num, level, node.start or 0, "Redundant lookaround, use \\B")
                )
        else:
            errs.append(
                (
                    num,
                    level,
                    node.start or 0,
                    "Redundant lookaround, use %s directly" % body[0].data,
                )
            )


def groups_check_superfluous_capture(reg, errs, expected_groups):
    # https://github.com/pygments/pygments/pull/3232
    num = "129"
    level = logging.WARNING
    msg = (
        "Superfluous capture group, the token action does not use it: "
        "use a non-capturing group (?:...) or drop the parentheses"
    )

    # When bygroups() consumes the captured text, the groups are needed.
    if expected_groups:
        return

    # Backreferences (\1, (?P=name), (?(1)...)) rely on the group numbering, so
    # the capturing groups are load-bearing; don't touch them.
    if list(
        find_all_by_type(
            reg,
            (Other.Backref, Other.Open.ExistsNamed, Other.Open.Exists),
        )
    ):
        return

    for cap in find_all_by_type(reg, Other.Open.Capturing):
        errs.append((num, level, cap.start or 0, msg))


_UNBOUNDED_REPETITION = (
    Other.Repetition.Star,
    Other.Repetition.NongreedyStar,
    Other.Repetition.Plus,
    Other.Repetition.NongreedyPlus,
)

_CONSUMING_GROUP = (
    Other.Open.Capturing,
    Other.Open.NonCapturing,
    Other.Open.NamedCapturing,
)


def _is_unbounded_repetition(node):
    """True for *, +, and open-ended {n,} (the quantifiers that can match an
    unbounded amount of text)."""
    if node.type in _UNBOUNDED_REPETITION:
        return True
    return node.type is Other.Repetition.Curly and node.max is None


def _body_is_ambiguously_repeatable(group):
    """True when a group's whole body reduces to a single unbounded repetition
    (possibly through nested single-child groups, or via an alternation branch).

    That is the shape that makes ``(<group>)+`` catastrophic: the inner
    quantifier can split the same input in exponentially many ways because no
    fixed text delimits successive iterations. Bodies with a mandatory literal
    part (e.g. ``ab+``) or single-character alternations (e.g. ``a|b``) are not
    ambiguous and are intentionally left alone to avoid false positives.
    """
    children = group.children
    # Unwrap chains of single-child groups, e.g. (?:(a+))+.
    while len(children) == 1 and children[0].type in _CONSUMING_GROUP:
        children = children[0].children
    if len(children) != 1:
        return False
    child = children[0]
    if _is_unbounded_repetition(child):
        return True
    if child.type is Other.Alternation:
        for branch in child.children:
            if len(branch.children) == 1 and _is_unbounded_repetition(
                branch.children[0]
            ):
                return True
    return False


def check_nested_quantifier_redos(reg, errs):
    num = "130"
    level = logging.WARNING
    msg = "Nested quantifier can cause catastrophic backtracking (ReDoS)"

    for rep in find_all_by_type(reg, Other.Repetition):
        if not _is_unbounded_repetition(rep):
            continue
        if len(rep.children) != 1:
            continue
        atom = rep.children[0]
        if atom.type not in _CONSUMING_GROUP:
            continue
        if _body_is_ambiguously_repeatable(atom):
            errs.append((num, level, atom.start or 0, msg))


def _foldable_alternation_atom(atom):
    """Return True when ``atom`` is a single character (or builtin class) that
    keeps its meaning inside ``[...]``, so a branch consisting solely of it can
    be folded into a character class."""
    if atom.type in Other.BuiltinCharclass:
        return True
    if atom.type in (Other.Tab, Other.Newline):
        return True
    if atom.type in Other.Literal:
        # Characters that change meaning inside ``[...]`` must not be folded:
        # ']' closes the class, '-' would form a range (1|-|9 -> [1-9]!), and a
        # leading '^' negates it. The lexer currently types most of these as
        # Other.Literals rather than Other.Literal, but guard explicitly so the
        # safety does not depend on tokenizer internals.
        return atom.data not in ("]", "-", "^")
    return False


# Metacharacters that need a backslash outside a class but are plain literals
# inside one, so the escape is redundant in the suggested ``[...]``. ']', '^'
# and '-' are deliberately excluded: unescaping them would close, negate or
# turn the class into a range.
_CLASS_REDUNDANT_ESCAPE = frozenset(".+*?(){}|$")


def _render_charclass_member(atom):
    """Render ``atom`` as it should appear inside a suggested character class,
    dropping backslashes that become redundant there (e.g. ``\\.`` -> ``.``)."""
    data = atom.data
    if len(data) == 2 and data[0] == "\\" and data[1] in _CLASS_REDUNDANT_ESCAPE:
        return data[1]
    return data


def check_single_char_alternation(reg, errs):
    num = "131"
    level = logging.WARNING
    msg = "Single-character alternation, use a character class %s instead"

    for alt in find_all_by_type(reg, Other.Alternation):
        atoms = []
        for branch in alt.children:
            if len(branch.children) != 1:
                break
            atom = branch.children[0]
            if not _foldable_alternation_atom(atom):
                break
            atoms.append(atom)
        else:
            # An alternation always has at least two branches; guard anyway.
            if len(atoms) >= 2:
                suggestion = (
                    "[" + "".join(_render_charclass_member(a) for a in atoms) + "]"
                )
                errs.append((num, level, alt.start or 0, msg % suggestion))


def check_quantified_lookaround(reg, errs):
    num = "132"
    level = logging.WARNING
    # A lookaround matches no characters, so a quantifier on it is always a
    # mistake, but the consequence differs. When at least one iteration is
    # required (+, {n}, {n,} with n>=1) the assertion still applies and the
    # quantifier is merely redundant. When zero iterations are allowed
    # (*, ?, {0,m}) the assertion can be skipped entirely, which silently
    # disables it -- a behaviour change rather than a no-op.
    redundant_msg = "Redundant quantifier on a zero-width lookaround assertion"
    disabling_msg = (
        "Quantifier makes a zero-width lookaround assertion optional, " "disabling it"
    )

    lookarounds = (
        Other.Open.Lookahead,
        Other.Open.NegativeLookahead,
        Other.Open.Lookbehind,
        Other.Open.NegativeLookbehind,
    )
    # Quantified anchors (\b+, ^?) are rejected by the engine before they ever
    # reach us, so only lookaround groups need checking here.
    for rep in find_all_by_type(reg, Other.Repetition):
        if len(rep.children) != 1:
            continue
        atom = rep.children[0]
        if atom.type in lookarounds:
            msg = disabling_msg if rep.min == 0 else redundant_msg
            errs.append((num, level, atom.start or 0, msg))


def check_redundant_noncapturing_group(reg, errs):
    num = "133"
    level = logging.WARNING
    msg = "Redundant non-capturing group, the (?:...) can be removed"

    for group in find_all_by_type(reg, Other.Open.NonCapturing):
        parent = group.parent()
        quantified = parent is not None and parent.type in Other.Repetition
        children = group.children
        single = len(children) == 1
        child = children[0] if single else None

        if quantified:
            # A group earns its keep only by binding the quantifier to more than
            # a single atom. One plain atom means (?:X)q == Xq, but an already
            # quantified atom ((?:a+)+ would merge into an illegal a++), an
            # alternation ((?:a|b)+) or a zero-width anchor ((?:^)+ would become
            # the illegal ^+) must keep the group.
            redundant = (
                single
                and child.type is not Other.Alternation
                and child.type not in Other.Repetition
                and child.type not in Other.Anchor
            )
        elif single and child.type is Other.Alternation:
            # A bare alternation needs the group for precedence against any
            # neighbouring atoms; it is only redundant when it is the whole
            # pattern, e.g. (?:a|b) but not x(?:a|b)y.
            redundant = parent is reg and len(reg.children) == 1
        else:
            # Unquantified concatenation is associative, so the group boundary is
            # invisible: (?:ab) == ab, x(?:ab)y == xaby.
            redundant = True

        if redundant:
            errs.append((num, level, group.start or 0, msg))


def manual_check_for_empty_string_match(reg, errs, raw_pat):
    # Skip the check in the following conditions:
    # * Rules that use a callback, since they're used for indentation
    #   tracking in SassLexer (and friends).
    if not isinstance(raw_pat[1], Token.__class__):
        return
    # * Rules with a state transition.  However, the empty pattern is
    #   disallowed, because that should be using default().
    if raw_pat[0] != "" and len(raw_pat) > 2:
        return

    regex = re.compile(raw_pat[0])
    # Either match on empty string, or empty string at the end of a word
    if regex.match("") or regex.match("a", 1):
        errs.append(("999", logging.ERROR, 0, "Matches empty string"))
    # remove_error(errs, '103')


def run_all_checkers(regex, expected_groups=None):
    errs = []
    for k, f in globals().items():
        if k.startswith("check_"):
            # print 'running', k, regex
            try:
                f(regex, errs)
            except Exception as e:
                errs.append(
                    (
                        "999",
                        logging.ERROR,
                        0,
                        "Checker %s encountered error parsing: %s" % (f, repr(e)),
                    )
                )
        elif k.startswith("bygroups_check_") and expected_groups:
            try:
                f(regex, errs, expected_groups)
            except Exception as e:
                errs.append(
                    (
                        "999",
                        logging.ERROR,
                        0,
                        "Checker %s encountered error parsing: %s" % (f, repr(e)),
                    )
                )
        elif k.startswith("groups_check_"):
            try:
                f(regex, errs, expected_groups)
            except Exception as e:
                errs.append(
                    (
                        "999",
                        logging.ERROR,
                        0,
                        "Checker %s encountered error parsing: %s" % (f, repr(e)),
                    )
                )
    return errs


def main(args):
    if not args:
        regex = r"(foo|) [a-Mq-&]"
    else:
        regex = args[0]
    for num, severity, pos1, text in run_all_checkers(Regex.get_parse_tree(regex)):
        print("%s%s:%s:%s" % (logging.getLevelName(severity)[0], num, pos1, text))


if __name__ == "__main__":
    main(sys.argv[1:])
