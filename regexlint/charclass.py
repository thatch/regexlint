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

from regexlint.parser import WHITESPACE, DIGITS, WORD, CharClass
from regexlint.util import build_ranges, esc

__all__ = ['simplify_charclass', 'charclass_score', 'build_output',
           'WontOptimize']

CATS = {
    '\\s': map(ord, WHITESPACE),
    '\\d': map(ord, DIGITS),
    '\\w': map(ord, WORD),
    '\\S': [i for i in range(256) if chr(i) not in WHITESPACE],
    '\\D': [i for i in range(256) if chr(i) not in DIGITS],
    '\\W': [i for i in range(256) if chr(i) not in WORD],
}

HEX = set(map(ord, '0123456789abcdef'))
ALNUM = set(range(ord('a'), ord('z')+1)) | set(map(ord, '0123456789'))

class WontOptimize(Exception):
    pass

def simplify_charclass(matching_codes, ignorecase=False):
    """Given a sequence of ordinals, return a (seq, negated) tuple.

    `ignorecase` is whether the regex flags include re.IGNORECASE.

    If the class shouldn't be optimized, raises WontOptimize with a basic reason
    string.
    """
    # HACK: Don't simplify something that looks fairly like a hex digit pattern.
    # They look arguably prettier as '0-9a-f' than '\da-f'
    if (len(HEX & set(matching_codes)) == len(HEX) and
        ord('g') not in matching_codes):
        raise WontOptimize('Hex digit')
    if (len(ALNUM & set(matching_codes)) == len(ALNUM) and ord('_') not in
        matching_codes):
        raise WontOptimize('Alphanumeric without _')

    if ignorecase:
        matching_codes = [lowercase_code(i) for i in matching_codes]
        base_set = set(map(lowercase_code, range(256)))
    else:
        base_set = set(range(256))

    # Tries all possibilities of categories first.
    keys = sorted(CATS.keys(), reverse=True)
    #print "keys", keys
    # Strategy: since we have a small number of categories, try each of them to
    # see if it's legal; add in remaining ranges; score.
    # TODO negated too.
    possibilities = []
    for negated in (0, 1):
        for i in range(2**len(keys)):
            chosen_keys = [keys[b] for b in range(len(keys)) if i & 1<<b]
            # Humans are terrible at double-negatives.  If this involves a
            # negation of the charclass as well as the category, tough cookies.
            # This will cause suggested _expansion_ of any such uses already in
            # the codebase, which should be ignored by the caller.
            if negated:
                if any(k[1].isupper() for k in chosen_keys):
                    continue

            if negated:
                matching_set = base_set - set(matching_codes)
            else:
                matching_set = set(matching_codes)
            chosen_set = set()
            for k in chosen_keys:
                chosen_set |= set(CATS[k]) & base_set
            # True iff. the chosen categories fit entirely in the target.
            if (len(matching_set & chosen_set) == len(chosen_set)):
                matching_set -= chosen_set
                r = build_ranges(matching_set)
                r[:0] = chosen_keys
                discount = 1 if chosen_keys == ['\w', '\W'] else 0

                if r:
                    possibilities.append((charclass_score(r, negated) - discount,
                                          r, negated))

    # There will always be one, since we include no-categories above, and it's
    # not on the WontOptimize list.
    possibilities.sort()
    return (possibilities[0][1], possibilities[0][2])


def charclass_score(items, negated=False):
    r"""Returns a number representing complexity of this charclass.

    items is a list of either categories (like '\s'), literals (numeric), or
    2-tuples representing a range (which is assumed of homogeneous class.
    """

    if isinstance(items, CharClass):
        # This is for testing -- given a parsed CharClass, returns the length of
        # the string inside []
        return items.end - items.start - 2

    return len(build_output(items)) + (negated and 1 or 0)


def build_output(items):
    def _esc(c):
        # Single quotes are two chars in reprs.  The others are metachars in
        # character classes.
        return esc(c, '\'-[]')

    buf = []
    for i in items:
        if isinstance(i, tuple):
            if i[0] != i[1] - 1:
                # todo escape
                buf.append('%s-%s' % (_esc(chr(i[0])), _esc(chr(i[1]))))
            else:
                buf.append(_esc(chr(i[0])) + _esc(chr(i[1])))
        elif isinstance(i, str):
            buf.append(i)
        else:
            buf.append(_esc(chr(i)))
    return ''.join(buf)


def lowercase_code(i):
    if 65 <= i <= 90:
        return i + 32
    return i
