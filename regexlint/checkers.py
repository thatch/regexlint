import logging
from regexlint.parser import *

# no nulls in regex (per docs)
# no funny literals (use \xnn)
# charclass range only on alpha
# no empty alternation
# no alternation with out of order prefix

def _has_end_anchor(reg):
    if not isinstance(reg, Node):
        return False

    return any(_has_end_anchor(s) for s in reg.alternations)


def check_no_nulls(reg, errs):
    num = '101'
    level = logging.ERROR
    msg = 'Null characters not allowed (python docs)'
    if '\x00' in reg.raw:
        errs.append((num, level, msg))

def check_no_newlines(reg, errs):
    num = '102'
    level = logging.ERROR
    msg = 'Newline characters not allowed (java compat)'
    if '\n' in reg.raw:
        errs.append((num, level, msg))

def check_no_empty_alternations(reg, errs):
    num = '103'
    level = logging.ERROR
    msg = 'Empty string allowed in alternation starting at position %d, use *'
    for n in all_nodes(reg):
        #print "Node", n
        if [] in n.alternations:
            errs.append((num, level, msg % (n.start or 0)))

def check_charclass_homogeneous_ranges(reg, errs):
    num = '104'
    level = logging.ERROR
    msg = 'Range in character class is not homogeneous near position %d'
    for c in all_charclass(reg):
        for p in c.chars:
            if isinstance(p, CharRange):
                if p.a[0] in Literal and p.b[0] in Literal:
                    # should be single character data, can compare
                    assert len(p.a[1] == 1)
                    assert len(p.b[1] == 1)
                    if charclass(p.a[1]) != charclass(p.b[1]):
                        errs.append((num, level, msg % c.start))
                    # only positive ranges are allowed.
                    if ord(p.a[1]) >= ord(p.b[1]):
                        errs.append((num, level, 'order %d' % c.start))
                elif p.a[0] not in Literal and p.b[0] not in Literal:
                    # punctuation range?
                    errs.append((num, level, msg % c.start))
                else:
                    # strange range.
                    errs.append((num, level, msg % c.start))

def check_prefix_ordering(reg, errs):
    """
    Checks for things of the form a|ab, which should be ab|a due to python
    quirks.
    """
    for n in all_nodes(reg):
        pass

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

    if isinstance(i[0], Node):
        # BAH
        raise NotImplementedError("Can't handle alternations with Nodes")
    elif isinstance(i[0], CharRange):
        # BAH
        raise NotImplementedError("Can't handle alternations with CharRange")
    else:
        # a literal, I hope!
        for j in _alternation_helper(i[1:]):
            yield i[0][1] + j
        

def all_nodes(regex_root):
    s = [regex_root]
    while s:
        i = s.pop(0)
        assert isinstance(i, Node)
        for alt in i.alternations:
            for x in alt:
                if isinstance(x[1], Node):
                    s.append(x[1])
        yield i

def all_charclass(regex_root):
    s = [regex_root]
    while s:
        i = s.pop(0)
        assert isinstance(i, Node)
        for alt in i.alternations:
            for x in alt:
                if isinstance(x[1], Node):
                    s.append(x[1])
                elif isinstance(x[1], CharRange):
                    yield x[1]

def find_by_type(regex_root, t):
    for n in all_nodes(regex_root):
        for alt in n.alternations:
            for x in alt:
                if x[0] == t:
                    return x[1]
    return None

def run_all_checkers(regex):
    errs = []
    for k, f in globals().iteritems():
        if k.startswith('check_'):
            #print 'running', k
            try:
                f(regex, errs)
            except Exception, e:
                errs.append(('999', logging.ERROR, "Checker %s encountered error parsing: %s" % (f, repr(e))))
    return errs

if __name__ == '__main__':
    print run_all_checkers(Regex().get_parse_tree(r'(foo|) [a-Mq-&]'))


