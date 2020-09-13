=========
Regexlint
=========

Regexlint is intended to be run as a linter against an importable Pygments
lexer, and flag problems that will prevent the lexer from performing well (since
we don't have branch coverage for lexers :)

As a simple example, alternations are first match, so it will flag this as never
matching "elseif"::

    (else|elseif)

It also understands some Pygments internals, for example ``bygroups(...)```
needs to have the same number of args as the regex has capture groups.  Too many
will result in duplicate text; too few will result in missing text.  There
should also not be any gaps between the capture groups, so this example flags
two problems::

    (r'(foo)\s+(bar)', bygroups(Blah)),


Usage
=====

::

    make demo
        or
    regexlint pygments.lexers.web:HtmlLexer
        or
    python3 regexlint/cmdline.py pygments.lexers.web


Todo
====

* Figure out which phase should remove unnecessary backslashes
* Write the alternation expander, so that ([ax]|a[bc]) fails the alternation
  order checks
* Make more general than just for Pygments


License
=======

This project is licensed under the Apache Public License, see COPYING
