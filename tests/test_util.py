# Copyright 2012 Google Inc.
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

from regexlint.util import *
from unittest import TestCase

class CmdlineTests(TestCase):
    def test_consistent_repr_empty(self):
        golden = r"''"
        self.assertEquals(golden, consistent_repr(eval(golden)))

    def test_consistent_repr(self):
        golden = r"""'azAZ09!#-$_\\/\'"\n\t\x02\xf3'"""
        self.assertEquals(golden, consistent_repr(eval(golden)))

    def test_consistent_repr_unicode(self):
        golden = r"u'text\u1234text'"
        print repr(eval(golden))
        self.assertEquals(golden, consistent_repr(eval(golden)))

    def test_consistent_repr_wide_unicode(self):
        try:
            unichr(0x100001)
        except:
            # Python build doesn't handle 32-bit unicode
            # TODO: say that the test was skipped
            pass
        else:
            # Python build handles 32-bit unicode
            golden = r"u'text\U00101234text'"
            print repr(eval(golden))
            self.assertEquals(golden, consistent_repr(eval(golden)))
