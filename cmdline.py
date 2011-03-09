import sys
import re
import logging

from pygments.lexer import RegexLexer
from pygments.token import Token
from regexlint import Regex
from checkers import run_all_checkers

def import_mod(m):
    mod = __import__(m)
    for part in m.split('.')[1:]:
        mod = getattr(mod, part)
    return mod

def main(argv):
    # currently just a list of module names.
    for module in argv:
        mod = import_mod(module)
        for k, v in mod.__dict__.iteritems():
            if hasattr(v, '__bases__') and issubclass(v, RegexLexer) and v.tokens:
                check_lexer(k, v)

def shorten(s):
    if len(s) < 76:
        return repr(s)
    else:
        return repr(s)[:72] + '...'

def remove_error(errs, *nums):
    for i in range(len(errs)-1, -1, -1):
        if errs[i][0] in nums:
            del errs[i]

def check_lexer(lexer_name, cls):
    #print lexer_name
    #print cls().tokens
    has_errors = False
    for state, pats in cls().tokens.iteritems():
        for i, pat in enumerate(pats):
            #print repr(pat[0])
            errs = run_all_checkers(Regex().get_parse_tree(pat[0]))
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
                for num, severity, text in errs:
                    print '%s%s:%s:%s:%d: %s' % (
                        (severity >= logging.ERROR and 'E' or 'W'), num,
                        lexer_name, state, i+1, text)
                print '  ' + shorten(pat[0])
    if not has_errors:
        print lexer_name, "OK"


if __name__ == '__main__':
    main(sys.argv[1:])
