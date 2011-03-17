import sys
import re
import logging

from pygments.lexer import RegexLexer
from pygments.token import Token
from regexlint import Regex, run_all_checkers
from regexlint.indicator import find_offending_line, mark

def import_mod(m):
    mod = __import__(m)
    for part in m.split('.')[1:]:
        mod = getattr(mod, part)
    return mod

def main(argv):
    # currently just a list of module names.
    for module in argv:
        mod = import_mod(module)
        print "Module", module
        if hasattr(mod, '__all__'):
            check_lexers(mod, mod.__all__)
        else:
            check_lexers(mod, mod.__dict__.keys())

def check_lexers(mod, lexer_names):
    for k in lexer_names:
        v = getattr(mod, k)
        if hasattr(v, '__bases__') and issubclass(v, RegexLexer) and v.tokens:
            check_lexer(k, v, mod.__file__)

def shorten(s):
    if len(s) < 76:
        return repr(s)
    else:
        return repr(s)[:72] + '...'

def remove_error(errs, *nums):
    for i in range(len(errs)-1, -1, -1):
        if errs[i][0] in nums:
            del errs[i]

def check_lexer(lexer_name, cls, mod_path):
    #print lexer_name
    #print cls().tokens
    has_errors = False
    if cls.flags & re.VERBOSE:
        print "GRR", lexer_name, "uses verbose mode"
        return
    for state, pats in cls().tokens.iteritems():
        for i, pat in enumerate(pats):
            #print repr(pat[0])
            reg = Regex().get_parse_tree(pat[0])
            # TODO check for verbose mode here.
            errs = run_all_checkers(reg)
            # Note, things like '#pop' and 'next-state' get a pass on this, as
            # do callback functions, since they are mostly used for advanced
            # features in indent-dependent languages.
            if len(pat) < 3 and isinstance(pat[1], Token):
                if re.compile(pat[0]).match(''):
                    errs.append(('999', logging.ERROR, 'Matches empty string'))
                #remove_error(errs, '103')
            
            errs.sort(key=lambda k: (k[1], k[0]))
            if errs:
                has_errors = True
                #print "Errors in", lexer_name, state, "pattern", i
                for num, severity, pos1, text in errs:
                    foo = find_offending_line(mod_path, lexer_name, state, i, pos1)
                    if foo:
                        line = 'L' + str(foo[0])
                    else:
                        line = 'pat#' + str(i+1)
                    print '%s%s:%s:%s:%s: %s' % (
                        (severity >= logging.ERROR and 'E' or 'W'), num,
                        lexer_name, state, line, text)
                    if foo:
                        mark(*foo)
                    else:
                        print 'Y  ' + shorten(pat[0])
    if not has_errors:
        print lexer_name, "OK"


if __name__ == '__main__':
    main(sys.argv[1:])
