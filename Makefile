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

PYTHON?=python
NOSETESTS?=nosetests
FIGLEAF?=figleaf
FIGLEAF2HTML?=figleaf2html

.PHONY: all
all:

.PHONY: test
test:
	$(NOSETESTS)

.PHONY: demo
demo:
	$(PYTHON) cmdline.py $$($(PYTHON) -c 'from pygments.lexers._mapping import LEXERS; print "\n".join(set([i[0] for i in LEXERS.values()]))')

.PHONY: selfdemo
selfdemo:
	$(PYTHON) cmdline.py regexlint.parser

.PHONY: coverage
coverage:
	rm -rf .figleaf html
	$(FIGLEAF) `which $(NOSETESTS)`
	$(FIGLEAF2HTML) -x figleaf_exclude

.PHONY: updatecopyright
updatecopyright: COPYING Makefile *.py */*.py
	export THIS_YEAR=$$(date +%Y) && \
	sed -i.bak \
		-e "s/Copyright \(....\) Google/Copyright \\1-$$THIS_YEAR Google/" \
		-e "s/Copyright \(....-\)\(....\) Google/Copyright \\1$$THIS_YEAR Google/" \
		-e "s/Copyright $${THIS_YEAR}-$${THIS_YEAR} Google/Copyright $$THIS_YEAR Google/" \
		$^
