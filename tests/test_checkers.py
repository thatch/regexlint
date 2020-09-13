# Copyright 2011-2014 Google Inc.
# Copyright 2018 Tim Hatch
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
from unittest import TestCase

from pygments.token import Name, Punctuation, Text, Token

from regexlint.checkers import (
    bygroups_check_no_capture_group_in_repetition,
    bygroups_check_no_python_named_capture_groups,
    bygroups_check_overlap,
    bygroups_check_toknum,
    check_bad_flags,
    check_charclass_case_insensitive_overlap,
    check_charclass_homogeneous_ranges,
    check_charclass_len,
    check_charclass_negation,
    check_charclass_overlap,
    check_charclass_simplify,
    check_multiline_anchors,
    check_no_bels,
    check_no_consecutive_dots,
    check_no_empty_alternations,
    check_no_newlines,
    check_no_nulls,
    check_prefix_ordering,
    check_redundant_repetition,
    check_single_character_classes,
    check_suspicious_anchors,
    check_unescaped_braces,
    manual_check_for_empty_string_match,
    run_all_checkers,
)
from regexlint.parser import Regex, fmttree


class CheckersTests(TestCase):
    def test_null(self):
        r = Regex.get_parse_tree("a\x00b")
        errs = []
        check_no_nulls(r, errs)
        self.assertEqual(len(errs), 1)

    def test_newline(self):
        r = Regex.get_parse_tree("a\nb")
        errs = []
        check_no_newlines(r, errs)
        self.assertEqual(len(errs), 1)

    def test_newline_ok_in_verbose(self):
        r = Regex.get_parse_tree("a\nb", re.VERBOSE)
        errs = []
        check_no_newlines(r, errs)
        self.assertEqual(len(errs), 0)

    def test_newline_ok_in_verbose2(self):
        r = Regex.get_parse_tree("(?x)a\nb")
        errs = []
        check_no_newlines(r, errs)
        self.assertEqual(len(errs), 0)

    def test_empty_alternation(self):
        r = Regex.get_parse_tree(r"(a|)")
        print("\n".join(fmttree(r)))
        errs = []
        check_no_empty_alternations(r, errs)
        self.assertEqual(len(errs), 1)

    def test_empty_alternation_in_root(self):
        # special case because linenum is bogus on root.
        r = Regex.get_parse_tree(r"a|")
        print("\n".join(fmttree(r)))
        errs = []
        check_no_empty_alternations(r, errs)
        self.assertEqual(len(errs), 1)

    def test_out_of_order_alternation_in_root(self):
        r = Regex.get_parse_tree(r"a|ab")
        print("\n".join(fmttree(r)))
        errs = []
        check_prefix_ordering(r, errs)
        self.assertEqual(len(errs), 1)

    def test_out_of_order_alternation_longer(self):
        r = Regex.get_parse_tree(r"(a|ab|c)")
        print("\n".join(fmttree(r)))
        errs = []
        check_prefix_ordering(r, errs)
        self.assertEqual(len(errs), 1)

    def test_out_of_order_alternation_location(self):
        r = Regex.get_parse_tree(r"(foo|bar|@|@@)")
        print("\n".join(fmttree(r)))
        errs = []
        check_prefix_ordering(r, errs)
        self.assertEqual(len(errs), 1)
        # location of the second one.
        self.assertEqual(errs[0][2], 11)

    def test_out_of_order_alternation_with_anchor_after(self):
        r = Regex.get_parse_tree(r"(a|ab)\b")
        print("\n".join(fmttree(r)))
        errs = []
        check_prefix_ordering(r, errs)
        print(errs)
        self.assertEqual(len(errs), 0)

    def test_out_of_order_crazy_complicated(self):
        r = Regex.get_parse_tree(r"""(!=|#|&&|&|\(|\)|\*|\+|,|-|-\.)""")
        # |->|\.|\.\.|::|:=|:>|:|;;|;|<|<-|=|>|>]|>}|\?|\?\?|\[|\[<|\[>|\[\||]|_|`|{|{<|\||\|]|}|~)''')
        print("\n".join(fmttree(r)))
        errs = []
        check_prefix_ordering(r, errs)
        self.assertEqual(len(errs), 1)

    def test_good_charclass(self):
        r = Regex.get_parse_tree(r"[a-zA-Z]")
        print("\n".join(fmttree(r)))
        errs = []
        check_charclass_homogeneous_ranges(r, errs)
        self.assertEqual(len(errs), 0)

    def test_good_charclass_hex(self):
        r = Regex.get_parse_tree(r"[\x00-\xff]")
        print("\n".join(fmttree(r)))
        errs = []
        check_charclass_homogeneous_ranges(r, errs)
        self.assertEqual(len(errs), 0)

    def test_bad_charclass(self):
        r = Regex.get_parse_tree(r"[A-z]")
        print("\n".join(fmttree(r)))
        print(r.children[0].chars)
        errs = []
        check_charclass_homogeneous_ranges(r, errs)
        print(errs)
        self.assertEqual(len(errs), 1)

    # Now that we run the regex through sre_parse, this is invalid.
    # def test_bad_charclass2(self):
    #    r = Regex.get_parse_tree(r'[z-A]')
    #    print('\n'.join(fmttree(r)))
    #    print(r.children[0].chars)
    #    errs = []
    #    check_charclass_homogeneous_ranges(r, errs)
    #    print(errs)
    #    self.assertEqual(len(errs), 2)

    def test_bad_charclass3(self):
        r = Regex.get_parse_tree(r"[\010-\020]")
        print("\n".join(fmttree(r)))
        print(r.children[0].chars)
        errs = []
        check_charclass_homogeneous_ranges(r, errs)
        print(errs)
        self.assertEqual(len(errs), 1)

    def test_good_unicode_charclass(self):
        r = Regex.get_parse_tree(u"[\u1000-\uffff]")
        print("\n".join(fmttree(r)))
        print(r.children[0].chars)
        errs = []
        check_charclass_homogeneous_ranges(r, errs)
        print(errs)
        self.assertEqual(len(errs), 0)

    def test_dash_begins_charclass(self):
        r = Regex.get_parse_tree(r"[-_]")
        print("\n".join(fmttree(r)))
        print(r.children[0].chars)
        errs = []
        check_charclass_homogeneous_ranges(r, errs)
        print(errs)
        self.assertEqual(len(errs), 0)
        self.assertEqual(len(r.children[0].chars), 2)
        self.assertEqual(r.children[0].chars[0].data, "-")
        self.assertEqual(r.children[0].chars[1].data, "_")

    def test_dash_ends_charclass(self):
        r = Regex.get_parse_tree(r"[_-]")
        print("\n".join(fmttree(r)))
        print(r.children[0].chars)
        errs = []
        check_charclass_homogeneous_ranges(r, errs)
        print(errs)
        self.assertEqual(len(errs), 0)
        self.assertEqual(len(r.children[0].chars), 2)
        self.assertEqual(r.children[0].chars[0].data, "_")
        self.assertEqual(r.children[0].chars[1].data, "-")

    def test_dash_after_range_charclass(self):
        r = Regex.get_parse_tree(r"[0-9-_]")
        print("\n".join(fmttree(r)))
        print(r.children[0].chars)
        errs = []
        check_charclass_homogeneous_ranges(r, errs)
        print(errs)
        self.assertEqual(len(errs), 0)
        self.assertEqual(len(r.children[0].chars), 3)
        self.assertEqual(r.children[0].chars[0].a.data, "0")
        self.assertEqual(r.children[0].chars[0].b.data, "9")
        self.assertEqual(r.children[0].chars[1].data, "-")
        self.assertEqual(r.children[0].chars[2].data, "_")

    def test_python_named_capture_groups(self):
        r = Regex.get_parse_tree(r"(?P<name>x)")
        print("\n".join(fmttree(r)))
        errs = []
        bygroups_check_no_python_named_capture_groups(r, errs, (Text,))
        self.assertEqual(len(errs), 1)

    def test_no_python_named_capture_groups(self):
        r = Regex.get_parse_tree(r"(x)")
        print("\n".join(fmttree(r)))
        errs = []
        bygroups_check_no_python_named_capture_groups(r, errs, (Text,))
        self.assertEqual(len(errs), 0)

    def test_run_all_checkers_no_errors(self):
        r = Regex.get_parse_tree(r"(x)")
        print("\n".join(fmttree(r)))
        errs = run_all_checkers(r)
        self.assertEqual(len(errs), 0)

    def test_run_all_checkers_errors(self):
        r = Regex.get_parse_tree(r"(?P<name>x|)")
        print("\n".join(fmttree(r)))
        errs = run_all_checkers(r, (Text,))
        self.assertEqual(len(errs), 3)

    def test_run_all_checkers_curly_ok(self):
        r = Regex.get_parse_tree(r"\{")
        print("\n".join(fmttree(r)))
        errs = run_all_checkers(r)
        print(errs)
        self.assertEqual(len(errs), 0)

    def test_run_all_checkers_curly(self):
        r = Regex.get_parse_tree(r"{")
        print("\n".join(fmttree(r)))
        errs = run_all_checkers(r)
        print(errs)
        self.assertEqual(len(errs), 1)

    def test_bygroups_check_overlap_success(self):
        r = Regex.get_parse_tree(r"(a)?(b)")
        print("\n".join(fmttree(r)))
        errs = []
        bygroups_check_overlap(r, errs, (Text, Text))
        self.assertEqual(len(errs), 0)

    def test_bygroups_check_overlap_fail(self):
        r = Regex.get_parse_tree(r"z(a)?z(b)z")
        print("\n".join(fmttree(r)))
        errs = []
        bygroups_check_overlap(r, errs, (Text, Text))
        print(errs)
        self.assertEqual(len(errs), 3)
        # 0 5 9

    def test_bygroups_check_overlap_fail2(self):
        r = Regex.get_parse_tree(r"\b(a)$")
        print("\n".join(fmttree(r)))
        errs = []
        bygroups_check_overlap(r, errs, (Text,))
        print(errs)
        self.assertEqual(len(errs), 0)

    def test_bygroups_check_overlap_nested_length(self):
        r = Regex.get_parse_tree(r"\b(a)((b)c)$")
        print("\n".join(fmttree(r)))
        errs = []
        bygroups_check_overlap(r, errs, (Text, Text))
        print(errs)
        self.assertEqual(len(errs), 1)
        self.assertEqual(errs[0][1], logging.INFO)

    def test_bygroups_check_overlap_nested_length2(self):
        r = Regex.get_parse_tree(r"\b(a)((b)c)$")
        print("\n".join(fmttree(r)))
        errs = []
        bygroups_check_overlap(r, errs, (Text, Text, Text))
        print(errs)
        self.assertEqual(len(errs), 1)
        self.assertEqual(errs[0][1], logging.ERROR)

    def test_bygroups_check_overlap_lookaround_ok(self):
        r = Regex.get_parse_tree(r"(?<!\.)(Class|Structure|Enum)(\s+)")
        print("\n".join(fmttree(r)))
        errs = []
        bygroups_check_overlap(r, errs, (Text, Text))
        print(errs)
        self.assertEqual(len(errs), 0)

    def test_bygroups_check_overlap_descending(self):
        r = Regex.get_parse_tree(r"(?:^|\b)(foo)")
        print("\n".join(fmttree(r)))
        errs = []
        bygroups_check_overlap(r, errs, (Text,))
        print(errs)
        self.assertEqual(len(errs), 0)

    def test_bygroups_check_overlap_descending2(self):
        r = Regex.get_parse_tree(r"(?:^|xx)(foo)")
        print("\n".join(fmttree(r)))
        errs = []
        bygroups_check_overlap(r, errs, (Text,))
        print(errs)
        self.assertEqual(len(errs), 1)

    def test_bygroups_check_overlap_descending_with_capture(self):
        r = Regex.get_parse_tree(
            r"(?:([A-Za-z_][A-Za-z0-9_]*)(\.))?([A-Za-z_][A-Za-z0-9_]*)"
        )
        print("\n".join(fmttree(r)))
        errs = []
        bygroups_check_overlap(r, errs, (Text, Text, Text))
        print(errs)
        self.assertEqual(len(errs), 0)

    def test_bygroups_check_overlap_descending_with_capture_and_gap(self):
        r = Regex.get_parse_tree(
            r"(?:([A-Za-z_][A-Za-z0-9_]*)x(\.))?([A-Za-z_][A-Za-z0-9_]*)"
        )
        print("\n".join(fmttree(r)))
        errs = []
        bygroups_check_overlap(r, errs, (Text, Text, Text))
        print(errs)
        self.assertEqual(len(errs), 1)

    def test_bygroups_check_overlap_but_none_for_token(self):
        r = Regex.get_parse_tree(r"(<(%)?)(\w+)((?(2)%)>)")
        print("\n".join(fmttree(r)))
        errs = []
        bygroups_check_overlap(r, errs, (Punctuation, None, Name, Punctuation))
        print(errs)
        self.assertEqual(len(errs), 0)

    def test_capture_group_in_repetition(self):
        r = Regex.get_parse_tree(r"(a)+((b)|c)*")
        print("\n".join(fmttree(r)))
        errs = []
        bygroups_check_no_capture_group_in_repetition(r, errs, (Text, Text))
        print(errs)
        self.assertEqual(len(errs), 3)

    def test_no_capture_group_in_repetition(self):
        # '?' is special-cased as being an okay repetition.
        r = Regex.get_parse_tree(r"(a)?(b)")
        print("\n".join(fmttree(r)))
        errs = []
        bygroups_check_no_capture_group_in_repetition(r, errs, (Text, Text))
        print(errs)
        self.assertEqual(len(errs), 0)

    def test_no_bels(self):
        r = Regex.get_parse_tree("a\bb")
        errs = []
        check_no_bels(r, errs)
        self.assertEqual(len(errs), 1)

    def test_consecutive_dots(self):
        r = Regex.get_parse_tree("a...")
        errs = []
        check_no_consecutive_dots(r, errs)
        print(errs)
        self.assertEqual(len(errs), 1)
        self.assertEqual(("111", logging.WARNING, 1), errs[0][:3])

    def test_toknum_good(self):
        r = Regex.get_parse_tree("(a)(b)")
        errs = []
        bygroups_check_toknum(r, errs, (Text, Text))
        print(errs)
        self.assertEqual(len(errs), 0)

    def test_toknum_too_few(self):
        r = Regex.get_parse_tree("(a)")
        errs = []
        bygroups_check_toknum(r, errs, (Text, Text))
        print(errs)
        self.assertEqual(len(errs), 1)
        self.assertEqual(("107", logging.ERROR, 0), errs[0][:3])

    def test_toknum_too_many(self):
        r = Regex.get_parse_tree("((a)b)")
        errs = []
        bygroups_check_toknum(r, errs, (Text,))
        print(errs)
        self.assertEqual(len(errs), 1)
        self.assertEqual(("107", logging.INFO, 0), errs[0][:3])

    def test_unnecessary_i_flag(self):
        r = Regex.get_parse_tree(r"(?i).")
        errs = []
        check_bad_flags(r, errs)
        print(errs)
        self.assertEqual(len(errs), 1)
        self.assertEqual(("113", logging.WARNING, 0), errs[0][:3])

    def test_necessary_i_flag(self):
        r = Regex.get_parse_tree(r"(?i)(a|b)")
        errs = []
        check_bad_flags(r, errs)
        print(errs)
        self.assertEqual(len(errs), 0)

    def test_necessary_i_flag_in_alternation1(self):
        r = Regex.get_parse_tree(r"(?i)[a-c]")
        errs = []
        check_bad_flags(r, errs)
        print(errs)
        self.assertEqual(len(errs), 0)

    def test_necessary_i_flag_in_alternation2(self):
        r = Regex.get_parse_tree(r"(?i)[a]")
        errs = []
        check_bad_flags(r, errs)
        print(errs)
        self.assertEqual(len(errs), 0)

    def test_necessary_i_flag_in_alternation3(self):
        r = Regex.get_parse_tree(r"(?i)[\x00-\x67]")
        errs = []
        check_bad_flags(r, errs)
        print(errs)
        self.assertEqual(len(errs), 0)

    def test_unnecessary_m_flag(self):
        r = Regex.get_parse_tree(r"(?m).")
        errs = []
        check_bad_flags(r, errs)
        print(errs)
        self.assertEqual(len(errs), 1)
        self.assertEqual(("113", logging.WARNING, 0), errs[0][:3])

    def test_necessary_i_flag2(self):
        r = Regex.get_parse_tree(r"(?m).$")
        errs = []
        check_bad_flags(r, errs)
        print(errs)
        self.assertEqual(len(errs), 0)

    def test_unnecessary_x_flag(self):
        r = Regex.get_parse_tree(r"(?x)foo[ ]")
        errs = []
        check_bad_flags(r, errs)
        print(errs)
        self.assertEqual(len(errs), 1)

    def test_necessary_x_flag(self):
        r = Regex.get_parse_tree(r"(?x)foo ")
        errs = []
        check_bad_flags(r, errs)
        print(errs)
        self.assertEqual(len(errs), 0)

    def test_necessary_x_flag_2(self):
        r = Regex.get_parse_tree(r"(?x)foo#comment")
        errs = []
        check_bad_flags(r, errs)
        print(errs)
        self.assertEqual(len(errs), 0)

    def test_suspicious_anchors_ok(self):
        r = Regex.get_parse_tree(r"^(a|b)$")
        errs = []
        check_suspicious_anchors(r, errs)
        print(errs)
        self.assertEqual(len(errs), 0)

    def test_suspicious_anchors(self):
        r = Regex.get_parse_tree(r"^a|b$")
        errs = []
        check_suspicious_anchors(r, errs)
        print(errs)
        self.assertEqual(len(errs), 1)

    def test_suspicious_whole_string_anchors(self):
        r = Regex.get_parse_tree(r"\Aa|b|c\Z")
        errs = []
        check_suspicious_anchors(r, errs)
        print(errs)
        self.assertEqual(len(errs), 1)

    def test_single_charclass_ok(self):
        r = Regex.get_parse_tree(r"[a-c]")
        errs = []
        check_single_character_classes(r, errs)
        print(errs)
        self.assertEqual(len(errs), 0)

    def test_single_charclass_bad(self):
        r = Regex.get_parse_tree(r"[a-a]")
        errs = []
        check_single_character_classes(r, errs)
        print(errs)
        self.assertEqual(len(errs), 1)

    def test_single_charclass_bad2(self):
        r = Regex.get_parse_tree(r"[ ]")
        errs = []
        check_single_character_classes(r, errs)
        print(errs)
        self.assertEqual(len(errs), 1)

    def test_single_charclass_ok_if_repeated(self):
        r = Regex.get_parse_tree(r"[ ]?")
        errs = []
        check_single_character_classes(r, errs)
        print(errs)
        self.assertEqual(len(errs), 0)

    def test_charclass_overlap(self):
        r = Regex.get_parse_tree(r"[\d\d]")
        errs = []
        check_charclass_overlap(r, errs)
        print(errs)
        self.assertEqual(len(errs), 1)

    def test_charclass_overlap2(self):
        r = Regex.get_parse_tree(r"[\d1]")
        errs = []
        check_charclass_overlap(r, errs)
        print(errs)
        self.assertEqual(len(errs), 1)

    def test_charclass_overlap3(self):
        r = Regex.get_parse_tree(r"[\dx]")
        errs = []
        check_charclass_overlap(r, errs)
        print(errs)
        self.assertEqual(len(errs), 0)

    def test_charclass_overlap4(self):
        r = Regex.get_parse_tree(r"[\Sx]")
        errs = []
        check_charclass_overlap(r, errs)
        print(errs)
        self.assertEqual(len(errs), 1)

    def test_single_entry_charclass(self):
        r = Regex.get_parse_tree(r"[0]")
        errs = []
        check_charclass_len(r, errs)
        print(errs)
        self.assertEqual(len(errs), 1)
        self.assertEqual(logging.WARNING, errs[0][1])

    def test_single_entry_charclass_ok(self):
        r = Regex.get_parse_tree(r"[ ]")
        errs = []
        check_charclass_len(r, errs)
        print(errs)
        self.assertEqual(len(errs), 1)
        self.assertEqual(logging.INFO, errs[0][1])

    def test_single_entry_optional_charclass(self):
        r = Regex.get_parse_tree(r"0[0]?")
        errs = []
        check_charclass_len(r, errs)
        print(errs)
        self.assertEqual(len(errs), 1)
        self.assertEqual(logging.INFO, errs[0][1])

    def test_single_entry_charclass_doesnt_fire_when_negated(self):
        r = Regex.get_parse_tree(r"[^0]")
        errs = []
        check_charclass_len(r, errs)
        print(errs)
        self.assertEqual(len(errs), 0)

    def test_single_entry_charclass_doesnt_fire_on_ranges(self):
        r = Regex.get_parse_tree(r"[a-b]")
        errs = []
        check_charclass_len(r, errs)
        print(errs)
        self.assertEqual(len(errs), 0)

    def test_single_entry_charclass_ok2(self):
        r = Regex.get_parse_tree(r"[#]", re.VERBOSE)
        errs = []
        check_charclass_len(r, errs)
        print(errs)
        self.assertEqual(len(errs), 1)
        self.assertEqual(logging.WARNING, errs[0][1])
        self.assertTrue("backslash" in errs[0][3])

    def test_negated_charclass_with_builtin_range(self):
        r = Regex.get_parse_tree(r"[^\s]")
        errs = []
        check_charclass_negation(r, errs)
        print(errs)
        self.assertEqual(len(errs), 1)

    def test_negated_charclass_with_multiple_builtin_range(self):
        r = Regex.get_parse_tree(r"[^\s\D]")
        errs = []
        check_charclass_negation(r, errs)
        print(errs)
        self.assertEqual(len(errs), 0)

    def test_negated_charclass_with_builtin_range2(self):
        r = Regex.get_parse_tree(r"[\s]")
        errs = []
        check_charclass_negation(r, errs)
        print(errs)
        self.assertEqual(len(errs), 0)

    def test_negated_charclass_only_bracket(self):
        r = Regex.get_parse_tree(r"[^]]+")
        errs = []
        check_charclass_negation(r, errs)
        print(errs)
        self.assertEqual(len(errs), 0)

    def test_charclass_case_insensitive_overlap_ok(self):
        r = Regex.get_parse_tree(r"(?i)[a-f]")
        errs = []
        check_charclass_case_insensitive_overlap(r, errs)
        print(errs)
        self.assertEqual(len(errs), 0)

    def test_charclass_case_insensitive_overlap_ok2(self):
        # TODO, catch this too, but suppress if not related to case-folding,
        # e.g. a-fa-z should trigger some other error, not this one, but
        # (?i)a-fA-Z should trigger this one.
        r = Regex.get_parse_tree(r"(?i)[a-fA-Z]")
        errs = []
        check_charclass_case_insensitive_overlap(r, errs)
        print(errs)
        self.assertEqual(len(errs), 0)

    def test_charclass_case_insensitive_overlap_flag(self):
        r = Regex.get_parse_tree(r"[0-9a-fA-F]", flags=re.I)
        errs = []
        check_charclass_case_insensitive_overlap(r, errs)
        print(errs)
        self.assertEqual(len(errs), 1)

    def test_charclass_case_insensitive_overlap_directive(self):
        r = Regex.get_parse_tree(r"(?i)[0-9a-fA-F]")
        errs = []
        check_charclass_case_insensitive_overlap(r, errs)
        print(errs)
        self.assertEqual(len(errs), 1)

    def test_charclass_case_insensitive_resets_properly(self):
        r = Regex.get_parse_tree(r"(?i)[a-f][a-f]")
        errs = []
        check_charclass_case_insensitive_overlap(r, errs)
        print(errs)
        self.assertEqual(len(errs), 0)

    def test_caret_in_multiline(self):
        r = Regex.get_parse_tree(r"^\s+", re.M)
        errs = []
        check_multiline_anchors(r, errs)
        print(errs)
        self.assertEqual(len(errs), 0)

    def test_caret_without_multiline(self):
        r = Regex.get_parse_tree(r"^\s+", 0)
        errs = []
        check_multiline_anchors(r, errs)
        print(errs)
        self.assertEqual(len(errs), 1)

    # Disabled \d optimization right now.
    # def test_charclass_simplify(self):
    #    r = Regex.get_parse_tree(r'[0-9_]', 0)
    #    errs = []
    #    check_charclass_simplify(r, errs)
    #    print(errs)
    #    self.assertEqual(len(errs), 1)
    #    self.assertTrue('[0-9_]' in errs[0][-1])
    #    self.assertTrue('[\\d_]' in errs[0][-1])

    def test_charclass_simplify_suggest_range(self):
        # Need to use ASCII mode to enable this checker.
        r = Regex.get_parse_tree(r"[01acb234]", re.A)
        errs = []
        check_charclass_simplify(r, errs)
        print(errs)
        self.assertEqual(len(errs), 1)
        self.assertTrue("0-4a-c" in errs[0][3], errs[0][3])

    def test_charclass_simplify_insensitive1(self):
        r = Regex.get_parse_tree(r"[a-z0-9_]", re.I | re.A)
        errs = []
        check_charclass_simplify(r, errs)
        print(errs)
        self.assertEqual(len(errs), 1)
        self.assertTrue("\\w" in errs[0][3], errs[0][3])

    def test_charclass_simplify_insensitive2(self):
        r = Regex.get_parse_tree(r"[A-Z0-9_]", re.I | re.A)
        errs = []
        check_charclass_simplify(r, errs)
        print(errs)
        self.assertEqual(len(errs), 1)
        self.assertTrue("\\w" in errs[0][3], errs[0][3])

    def test_charclass_simplify_insensitive3(self):
        r = Regex.get_parse_tree(r"[eE]", re.I | re.A)
        errs = []
        check_charclass_simplify(r, errs)
        print(errs)
        self.assertEqual(len(errs), 1)
        self.assertTrue("-> e" in errs[0][3], errs[0][3])

    def test_charclass_simplify_noop(self):
        r = Regex.get_parse_tree(r"[\d_]", 0)
        errs = []
        check_charclass_simplify(r, errs)
        print(errs)
        self.assertEqual(len(errs), 0)

    def test_unescaped_curly_brace(self):
        r = Regex.get_parse_tree(r"{", 0)
        errs = []
        check_unescaped_braces(r, errs)
        print(errs)
        self.assertEqual(len(errs), 1)

    def test_redundant_repetition(self):
        r = Regex.get_parse_tree(r"a{1}", 0)
        errs = []
        check_redundant_repetition(r, errs)
        print(errs)
        self.assertEqual(len(errs), 1)

    def test_redundant_repetition_ok(self):
        r = Regex.get_parse_tree(r"a{1,4}", 0)
        errs = []
        check_redundant_repetition(r, errs)
        print(errs)
        self.assertEqual(len(errs), 0)

    def test_redundant_repetition_star(self):
        r = Regex.get_parse_tree(r"a{0,1}", 0)
        errs = []
        check_redundant_repetition(r, errs)
        print(errs)
        self.assertEqual(len(errs), 1)

    def test_manual_empty_string(self):
        r = Regex.get_parse_tree("")
        errs = []
        manual_check_for_empty_string_match(r, errs, ("", Token))
        print(errs)
        self.assertEqual(len(errs), 1)

    def test_manual_empty_string_after_word(self):
        r = Regex.get_parse_tree(r"$\b")
        errs = []
        manual_check_for_empty_string_match(r, errs, (r"$\b", Token))
        print(errs)
        self.assertEqual(len(errs), 1)

    def test_manual_empty_string_when_pop(self):
        # default() is handled in cmdline.py
        r = Regex.get_parse_tree(r"")
        errs = []
        manual_check_for_empty_string_match(r, errs, (r"", Token, "#pop"))
        print(errs)
        self.assertEqual(len(errs), 1)

    def test_manual_zerowidth_match(self):
        # This one shouldn't produce an error.
        r = Regex.get_parse_tree(r"$\b")
        errs = []
        manual_check_for_empty_string_match(r, errs, (r"$\b", Token, "#pop"))
        print(errs)
        self.assertEqual(len(errs), 0)
