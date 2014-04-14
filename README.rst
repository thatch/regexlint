=========
Regexlint
=========

Regexlint will examine all regular expressions in an importable Pygments
lexer, and report things that are probably not doing what you think they're
doing.  For example, patterns like this (which will only match the first)::

    (else|elseif)

It can also warn about a few syntax problems, for example this has two
problems -- the ``\s+`` outside the groups, and not enough actions in bygroups
(this one needs two in the args to bygroups)::

    (r'(foo)\s+(bar)', bygroups(Blah)),


Usage
=====

::

    make demo
        or
    regexlint pygments.lexers.web:HtmlLexer
        or
    python2 regexlint/cmdline.py pygments.lexers.web


Todo
====

* Figure out which phase should remove unnecessary backslashes
* Write the alternation expander, so that ([ax]|a[bc]) fails the alternation
  order checks
* Make more general than just for Pygments


License
=======

This project is licensed under the Apache Public License, see COPYING
