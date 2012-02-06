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

from pygments.token import Other

def get_alternation_possibilities(alt):
    """
    alt is the 2d list, i.e. [['a'], ['a', 'b']]
    """
    for i in alt:
        for j in _alternation_helper(i):
            yield j

def _alternation_helper(i):
    if not i:
        yield ''
        return

    #if isinstance(i[0], Node):
    #    # BAH
    #    raise NotImplementedError("Can't handle alternations with Nodes")
    #elif isinstance(i[0], CharRange):
    #    # BAH
    #    raise NotImplementedError("Can't handle alternations with CharRange")
    #else:
    # a literal, I hope!
    for j in _alternation_helper(i[1:]):
        yield i[0][1] + j


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
    tab = {'\\t': '\t', '\\n': '\n', '\\\'': '\'', '\\"': '"'}
    if len(c) == 1:
        return ord(c)
    elif c in tab:
        return ord(tab[c])
    elif c[0] == '\\' and c[1] not in 'x01234567':
        c = c[1:] # unnecessary backslash?

    #print repr(c)
    return ord(eval("'%s'" % c))
    # TODO any other cases?

class Break(Exception): pass
