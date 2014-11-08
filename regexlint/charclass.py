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
from regexlint.util import build_ranges, esc, lowercase_code
from regexlint.bitvector import bitvector, unpack_bitvector

__all__ = ['simplify_charclass', 'charclass_score', 'build_output',
           'WontOptimize']

CATS = {
    '\\s': bitvector(map(ord, WHITESPACE)),
    # disabled as it's not more easily readable.
    #'\\d': bitvector(map(ord, DIGITS)),
    '\\w': bitvector(map(ord, WORD)),
    '\\S': bitvector([_ for _ in range(256) if chr(_) not in WHITESPACE]),
    '\\D': bitvector([_ for _ in range(256) if chr(_) not in DIGITS]),
    '\\W': bitvector([_ for _ in range(256) if chr(_) not in WORD]),
}

HEX = bitvector(map(ord, '0123456789abcdef'))
ALNUM = (bitvector(range(ord('a'), ord('z')+1)) |
         bitvector(map(ord, '0123456789')))
ASCII = (1<<256) - 1
INSENSITIVE_ASCII = bitvector(map(lowercase_code, range(256)))

class WontOptimize(Exception):
    pass

def simplify_charclass(matching_codes, ignorecase=False):
    """Given a sequence of ordinals, return a (seq, negated) tuple.

    `ignorecase` is whether the regex flags include re.IGNORECASE.

    If the class shouldn't be optimized, raises WontOptimize with a basic reason
    string.
    """
    if max(matching_codes) > 255:
        raise WontOptimize('Unicode')

    # HACK: Don't simplify something that looks fairly like a hex digit pattern.
    # They look arguably prettier as '0-9a-f' than '\da-f'
    bv = bitvector(matching_codes)
    if (bv & HEX) == HEX and ord('g') not in matching_codes:
        raise WontOptimize('Hex digit')
    if (bv & ALNUM) == ALNUM and ord('_') not in matching_codes:
        raise WontOptimize('Alphanumeric without _')

    if ignorecase:
        bv = bitvector(map(lowercase_code, matching_codes))
        base = INSENSITIVE_ASCII
    else:
        base = ASCII

    # Tries all possibilities of categories first.
    keys = sorted(CATS.keys(), reverse=True)
    # Strategy: since we have a small number of categories, try each of them to
    # see if it's legal; add in remaining ranges; score.
    # when negated=0, there are 64 (=2**6) combinations to check.
    # when negated=1, there are only 8 (=2**3) combinations.
    possibilities = []
    for negated in (0, 1):
        #  target is the set of all characters we want to match, and none of the
        #  ones we don't (note: for case-insensitive, we mask `chosen' before
        #  comparing later).
        if negated:
            if ignorecase:
                target = bitvector(map(
                    lowercase_code,
                    [i for i in range(256) if i not in unpack_bitvector(bv)]))
            else:
                target = base ^ (base & bv)
        else:
            target = bv

        for i in range(2**len(keys)):
            chosen_keys = [keys[b] for b in range(len(keys)) if i & 1<<b]
            # Humans are terrible at double-negatives.  If this involves a
            # negation of the charclass as well as the category, tough cookies.
            # This will cause suggested _expansion_ of any such uses already in
            # the codebase, which should be ignored by the caller.
            if negated:
                if any(k[1].isupper() for k in chosen_keys):
                    continue

            t = target
            chosen = 0
            for k in chosen_keys:
                chosen |= CATS[k]
            # N.b. don't need to conditionally lowercase_code here because all
            # our categories contain lower if they contain upper.
            chosen &= base

            # True iff. the chosen categories fit entirely in the target.
            if chosen & t == chosen:
                #print chosen_keys, "t", unpack_bitvector(t), unpack_bitvector(chosen)
                t ^= chosen
                #print "  ", unpack_bitvector(t)
                r = build_ranges(unpack_bitvector(t))
                r[:0] = chosen_keys
                discount = 1 if chosen_keys == ['\\w', '\\W'] else 0

                if r:
                    possibilities.append((charclass_score(r, negated) - discount,
                                          r, negated))

    #print "possibilities", possibilities
    # There will always be one, since we include no-categories above, and it's
    # not on the WontOptimize list.
    possibilities.sort(key=lambda i: i[0])
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
    """
    Given sorted input (ranges as tuples, categories as strings, or individual
    characters as ints), construct the output string.
    """
    def _esc(c):
        # Single quotes are two chars in reprs.  The others are metachars in
        # character classes (although '-' and '[' are not special in certain
        # positions, we never use that feature).
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

    # keep caret in its otherwise-chosen position, but escape if necessary
    if buf and buf[0].startswith('^'):
        buf.insert(0, '\\')
    return ''.join(buf)
