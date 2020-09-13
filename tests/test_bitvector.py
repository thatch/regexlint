# Copyright 2011-2014 Google Inc.
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

from unittest import TestCase

from regexlint.bitvector import bitvector, population, unpack_bitvector


class BitvectorTests(TestCase):
    def test_population(self):
        self.assertEqual(population(0), 0)
        self.assertEqual(population(1), 1)
        self.assertEqual(population(2), 1)
        self.assertEqual(population(3), 2)
        self.assertEqual(population(4), 1)
        self.assertEqual(population(254), 7)
        self.assertEqual(population(255), 8)
        self.assertEqual(population(1 << 1234), 1)

    def test_unpack_bitvector(self):
        for i in range(32):
            n = 1 << i
            lst = unpack_bitvector(n)
            self.assertEqual(len(lst), 1)
            self.assertEqual(lst[0], i)

    def test_pack_bitvector(self):
        for i in range(1 << 10):
            intermediate = unpack_bitvector(i)
            x = bitvector(intermediate)
            print(i, intermediate)
            self.assertEqual(i, x)
