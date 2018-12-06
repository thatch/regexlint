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

from __future__ import with_statement

from pygments.token import Other

def find_all(first, second=None):
    """Finds all descendants (inorder) of first, including itself.  If second
    is provided, stops when it is reached."""
    regex = first
    while regex and regex is not second:
        yield regex
        regex = regex.next()


def find_all_by_type(regex_root, t):
    for regex in find_all(regex_root):
        if regex.type in t:
            yield regex


def between(first, second):
    """Yields all nodes between first and second, not including either
    endpoint.  The special first value None means to start at the beginning,
    not including the root.  The special second value None means to go until
    the end, but either first or second must be provided."""
    if first is None:
        first = second
        while first.parent():
            first = first.parent()
        first = first.children[0]
    else:
        first = first.next_no_children()

    it = find_all(first, second)
    for i in it:
        yield i


def find_bad_between(first, second, fn):
    """Finds the first node in between(first, second) where fn returns True.
    If fn returns None, the node will be descended, False, it will be ignored.
    The default return value is None."""

    # Rather than a complex, fast solution, this simply walks all nodes, and
    # ignores the ones that already have a whitelisted parent.
    good_obj = None
    for j in between(first, second):
        #print "Intermediate", j, j.type
        if good_obj and j.is_descentant_of(good_obj):
            pass
        else:
            v = fn(j)
            if v == True:
                return j
            elif v == False:
                good_obj = j
            # else keep going


def has_width(node):
    """Helper for use with find_bad_between."""
    # returns True/False/None
    return width(node.type)


def fmttree(t):
    """Returns a list of lines containing a pretty-printed tree.
    The tree is any regex node, passed in as t.  Indent is two spaces.
    """
    if not hasattr(t, 'children'):
        return [repr(t)]

    r = []
    r.append('<%s type=%r data=%r>' % (t.__class__.__name__, t.type, t.data))
    for c in t.children:
        r.extend('  ' + f for f in fmttree(c))
    return r


def width(tok):
    """Returns whether the given token type might consume characters."""
    if (tok in (Other.Directive,
                Other.Open.Lookahead, Other.Open.NegativeLookahead,
                Other.Open.NegativeLookbehind, Other.Open.Lookbehind,
                Other.Comment) or (tok in Other.Anchor)):
        return False
    elif (tok in Other.Open or tok in Other.Alternation or tok in
          Other.Progression or tok in Other.Repetition):
        return None # unsure if it has width, must descend
    else:
        return True

def eval_char(c):
    """Returns the character code of the string s, which may contain
    escapes."""
    if len(c) == 1:
        return ord(c)
    elif c[-1] == "'":
        return ord("'")
    elif c[0] == '\\' and c[1] not in 'abtrnvfxuU01234567\\':
        c = c[1:] # unnecessary backslash?
    elif c == '\\u':
        # Hack for truncated unicode due to matching as Suspicious
        return ord('u')

    #print repr(c)
    if len(c) == 1 and ord(c) >= 128:
        return c

    try:
        return ord(eval("b'%s'" % c))
    except TypeError:
        # Probably a unicode escape.
        return ord(eval("u'%s'" % c))


class Break(Exception):
    pass


ESC_SPECIAL = {
    u'\r': '\\r',
    u'\n': '\\n',
    u'\t': '\\t',
    u'\\': '\\\\',
    u'\'': '\\\'',
    b'\r': '\\r',
    b'\n': '\\n',
    b'\t': '\\t',
    b'\\': '\\\\',
    b'\'': '\\\'',
}


def esc(c, also_escape=(), esc_special=ESC_SPECIAL):
    if c in esc_special:
        return esc_special[c]
    elif ord(c) > 0xFFFF:
        return '\\U%08x' % ord(c)
    elif isinstance(c, type(u'')) and ord(c) > 126:
        return '\\u%04x' % ord(c)
    elif ord(c) < 32 or ord(c) > 126:
        return '\\x%02x' % ord(c)
    elif c in also_escape:
        return '\\' + c
    else:
        if isinstance(c, bytes):
            return c.decode('latin-1')
        return c


def consistent_repr(s, escape=(), include_quotes=True):
    """Returns a string that represents repr(s), but without the logic that
    switches between single and double quotes.

    Equivalent to _codecs.escape_encode for ASCII strings (and this works on
    Unicode).
    """
    rep = []
    if include_quotes:
        if isinstance(s, bytes):
            rep.append('b')
        rep.append('\'')
    for i in range(len(s)):
        rep.append(esc(s[i:i+1], escape))
    if include_quotes:
        rep.append('\'')
    return ''.join(rep)


def shorten(text, start, end):
    """Returns a substring of text, so that its length is < 80 or so."""
    if len(text) < 76:
        return (text, start, end)

    start_cut = max(0, start - 36)
    end_cut = min(len(text), start + 36)
    cut_text = text[start_cut:end_cut]
    start -= start_cut
    end -= start_cut
    if start_cut != 0:
        cut_text = '...' + cut_text
        start += 3
        end += 3
    if end_cut != len(text):
        cut_text += '...'
    return (cut_text, start, end)


def get_module_text(mod):
    if '\n' in mod:
        mod_text = mod
    else:
        if mod.endswith('.pyc') or mod.endswith('.pyo'):
            mod = mod[:-1]
        with open(mod, 'r') as f:
            mod_text = f.read()
    return mod_text


def rindex(a, x):
    for i in range(len(a)-1, -1, -1):
        if a[i] == x:
            return i
    raise ValueError("Not found")


def charclass(c):
    if isinstance(c, int):
        c = chr(c)

    if 'A' <= c <= 'Z':
        return 'upper'
    elif 'a' <= c <= 'z':
        return 'lower'
    elif '0' <= c <= '9':
        return 'digit'
    else:
        return 'other'


def build_ranges(ord_seq):
    ranges = []

    prev_start = None
    prev_end = None
    prev_type = None

    for i in sorted(ord_seq):
        t = charclass(i)
        if (prev_type and prev_type != 'other' and t == prev_type and
            prev_end == i - 1):
            # extend
            prev_end = i
        else:
            if prev_type:
                if prev_start != prev_end:
                    ranges.append((prev_start, prev_end))
                else:
                    ranges.append(prev_start)
            prev_start = i
            prev_end = i
            prev_type = t

    if prev_type:
        if prev_start != prev_end:
            ranges.append((prev_start, prev_end))
        else:
            ranges.append(prev_start)

    return ranges

def lowercase_code(i):
    if 65 <= i <= 90:
        return i + 32
    return i
