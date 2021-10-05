#!/usr/bin/env python
"""OpenSSLVersion String Handling Tests

Rodrigo Ramirez Norambuena <a@rodrigoramirez.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
"""

from harness_shared import main
import unittest
from asterisk.opensslversion import OpenSSLVersion


class OpenSSLVersionTests(unittest.TestCase):
    def test_cmp_greater_than(self):
        v1 = OpenSSLVersion("1.0.1", None)
        v2 = OpenSSLVersion("1.0.0", None)
        self.assertTrue(v1 > v2)

    def test_cmp_less_than(self):
        v1 = OpenSSLVersion("1.0.1", None)
        v2 = OpenSSLVersion("1.0.0", None)
        self.assertTrue(v2 < v1)

    def test_cmp_equal(self):
        v1 = OpenSSLVersion("1.0.0", None)
        v2 = OpenSSLVersion("1.0.0", None)
        self.assertTrue(v1 == v2)

    def test_cmp_not_equal(self):
        v1 = OpenSSLVersion("1.0.1", None)
        v2 = OpenSSLVersion("1.0.0", None)
        self.assertTrue(v1 != v2)

if __name__ == "__main__":
    main()
