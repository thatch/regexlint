# Copyright 2014 Google Inc.
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

def bitvector(nums):
    i = 0
    for n in nums:
        i |= 1 << n
    return i

def unpack_bitvector(bv):
    ret = []
    code = 0
    mask = 1
    while mask <= bv:
        if bv & mask: ret.append(code)
        code += 1
        mask <<= 1
    return ret

def population(i):
    n = 0
    while i:
        if i & 1: n += 1
        i >>= 1
    return n

