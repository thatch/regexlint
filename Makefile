PYTHON?=python

.PHONY: all
all:

.PHONY: test
test:
	nosetests

.PHONY: demo
demo:
	$(PYTHON) cmdline.py $$(python -c 'from pygments.lexers._mapping import LEXERS; print "\n".join(set([i[0] for i in LEXERS.values()]))')
