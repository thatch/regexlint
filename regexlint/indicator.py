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

from regexlint.indicator_ast import find_offending_line, find_substr_pos
from regexlint.util import consistent_repr, shorten


def mark(lineno, d1, d2, text, output_stream):
    output_stream.write("  " + text + "\n")
    output_stream.write("  " + " " * d1 + '^' * (d2-d1) + ' ' + 'here\n')

def mark_str(d1, d2, text, output_stream):
    # Substract one for closing quote
    start = len(consistent_repr(text[:d1])) - 1
    end = len(consistent_repr(text[:d2])) - 1
    if start == end:
        # This handles the case where pos1 points to the end
        # of the string. Regex "|" with pos1 = 1.
        end += 1
    assert end > start
    text, start, end = shorten(consistent_repr(text), start, end)
    mark(-1, start, end, text, output_stream)
