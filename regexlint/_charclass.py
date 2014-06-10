from regexlint.parser import WHITESPACE, DIGITS, WORD, CharClass
from regexlint.util import build_ranges

CATS = {
    '\\s': map(ord, WHITESPACE),
    '\\d': map(ord, DIGITS),
    '\\w': map(ord, WORD),
    '\\S': [i for i in range(256) if chr(i) not in WHITESPACE],
    '\\D': [i for i in range(256) if chr(i) not in DIGITS],
    '\\W': [i for i in range(256) if chr(i) not in WORD],
}

def simplify_charclass(matching_codes):
    # Tries all possibilities of categories first.
    keys = CATS.keys()
    #print "keys", keys
    # Strategy: since we have a small number of categories, try each of them to
    # see if it's legal; add in remaining ranges; score.
    # TODO negated too.
    possibilities = []
    for negated in (0, 1):
        for i in range(2**len(keys)):
            chosen_keys = [keys[b] for b in range(len(keys)) if i & 1<<b]
            #print i, chosen_keys
            # TODO for each charclass.
            if negated:
                matching_set = set(range(256)) - set(matching_codes)
            else:
                matching_set = set(matching_codes)
            chosen_set = set()
            for k in chosen_keys:
                chosen_set |= set(CATS[k])
            if (len(matching_set & chosen_set) == len(chosen_set)):
                matching_set -= chosen_set
                r = build_ranges(matching_set)
                r[:0] = chosen_keys
                possibilities.append((charclass_score(r, negated), r, negated))

    # There will always be one, since we include no-categories above.
    possibilities.sort()
    return (possibilities[0][1], possibilities[0][2])


def charclass_score(items, negated=False):
    r"""Returns a number representing complexity of this charclass.

    items is a list of either categories (like '\s'), literals (numeric), or
    2-tuples representing a range (which is assumed of homogeneous class.
    """

    if isinstance(items, CharClass):
        print items
        return items.end - items.start - 2

    return len(build_output(items)) + (negated and 1 or 0)

def build_output(items):
    buf = []
    for i in items:
        if isinstance(i, tuple):
            if i[0] != i[1] - 1:
                # todo escape
                buf.append('%s-%s' % (_esc(chr(i[0])), _esc(chr(i[1]))))
            else:
                buf.append(_esc(chr(i[0])))
        elif isinstance(i, str):
            buf.append(i)
        else:
            buf.append(_esc(chr(i)))
    return ''.join(buf)

def _esc(c):
    if c == '\n':
        return '\\n'
    elif c in ('\\', '-'):
        return '\\' + c
    return c
