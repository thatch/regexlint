# Copyright 2011-2012 Google Inc.
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
    not including the root."""
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
    """Finds a node in between(first, second) where fn returns True.  If fn
    returns False, a node won't be descended. """
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
    # returns True/False/None
    return width(node.type)

def fmttree(t):
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
    elif c[0] == '\\' and c[1] not in 'abtrnvfx01234567':
        c = c[1:] # unnecessary backslash?

    #print repr(c)
    return ord(eval("'%s'" % c))
    # TODO any other cases?

class Break(Exception):
    pass

def consistent_repr(s):
    """Returns a string that represents repr(s), but without the logic that
    switches between single and double quotes."""
    special = {
        '\n': '\\n',
        '\t': '\\t',
        '\\': '\\\\',
        '\'': '\\\'',
    }
    rep = ['\'']
    if isinstance(s, unicode):
        rep.insert(0, 'u')
    for char in s:
        if char in special:
            rep.append(special[char])
        elif isinstance(s, unicode) and ord(char) > 0xFFFF:
            rep.append('\\U%08x' % ord(char))
        elif isinstance(s, unicode) and ord(char) > 126:
            rep.append('\\u%04x' % ord(char))
        elif ord(char) < 32 or ord(char) > 126:
            rep.append('\\x%02x' % ord(char))
        else:
            rep.append(char)
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
        with file(mod, 'r') as f:
            mod_text = f.read()
    return mod_text

def rindex(a, x):
    for i in range(len(a)-1, -1, -1):
        if a[i] == x:
            return i
    raise ValueError("Not found")

