#!/usr/bin/env python
"""SIPp Version String Handling Tests

Copyright (C) 2010, Digium, Inc.
Paul Belanger <pabelanger@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
"""

from harness_shared import main
import unittest
from asterisk.sippversion import SIPpVersion


class SIPpVersionTests(unittest.TestCase):
    def test_version(self):
        v = SIPpVersion("v3.2", None)
        self.assertEqual(str(v), "v3.2")
        self.assertEqual(v.concept, "v3")
        self.assertEqual(v.major, "2")
        self.assertEqual(v.minor, None)
        self.assertFalse(v.tls)
        self.assertFalse(v.pcap)

    def test_version2(self):
        v = SIPpVersion("v2.0.1", None)
        self.assertEqual(str(v), "v2.0.1")
        self.assertEqual(v.concept, "v2")
        self.assertEqual(v.major, "0")
        self.assertEqual(v.minor, "1")
        self.assertFalse(v.tls)
        self.assertFalse(v.pcap)

    def test_version3(self):
        v = SIPpVersion("v3.1", "TLS")
        self.assertEqual(str(v), "v3.1-TLS")
        self.assertEqual(v.concept, "v3")
        self.assertEqual(v.major, "1")
        self.assertEqual(v.minor, None)
        self.assertTrue(v.tls)
        self.assertFalse(v.pcap)

    def test_version4(self):
        v = SIPpVersion("v2.0.1", "TLS-PCAP")
        self.assertEqual(str(v), "v2.0.1-TLS-PCAP")
        self.assertEqual(v.concept, "v2")
        self.assertEqual(v.major, "0")
        self.assertEqual(v.minor, "1")
        self.assertTrue(v.tls)
        self.assertTrue(v.pcap)

    def test_version5(self):
        v = SIPpVersion("v3.2", "PCAP")
        self.assertEqual(str(v), "v3.2-PCAP")
        self.assertEqual(v.concept, "v3")
        self.assertEqual(v.major, "2")
        self.assertEqual(v.minor, None)
        self.assertFalse(v.tls)
        self.assertTrue(v.pcap)

    def test_version6(self):
        v = SIPpVersion(None, "PCAP")
        self.assertEqual(str(v), "PCAP")
        self.assertEqual(v.concept, None)
        self.assertEqual(v.major, None)
        self.assertEqual(v.minor, None)
        self.assertFalse(v.tls)
        self.assertTrue(v.pcap)

    def test_version7(self):
        v = SIPpVersion(None, "TLS")
        self.assertEqual(str(v), "TLS")
        self.assertEqual(v.concept, None)
        self.assertEqual(v.major, None)
        self.assertEqual(v.minor, None)
        self.assertTrue(v.tls)
        self.assertFalse(v.pcap)

    def test_version8(self):
        v = SIPpVersion(None, "TLS-PCAP")
        self.assertEqual(str(v), "TLS-PCAP")
        self.assertEqual(v.concept, None)
        self.assertEqual(v.major, None)
        self.assertEqual(v.minor, None)
        self.assertTrue(v.tls)
        self.assertTrue(v.pcap)

    def test_cmp(self):
        v1 = SIPpVersion("v3.2", None)
        v2 = SIPpVersion("v3.1", None)
        self.assertTrue(v1 > v2)

    def test_cmp2(self):
        v1 = SIPpVersion("v2.0.1", None)
        v2 = SIPpVersion("v3.1", None)
        self.assertTrue(v1 < v2)

    def test_cmp3(self):
        v1 = SIPpVersion("v3.1", None)
        v2 = SIPpVersion("v3.1", None)
        self.assertTrue(v1 == v2)

    def test_cmp4(self):
        v1 = SIPpVersion("v3.1", None)
        v2 = SIPpVersion("v3.1", None)
        self.assertFalse(v1 != v2)

    def test_cmp5(self):
        v1 = SIPpVersion("v3.1", "TLS")
        v2 = SIPpVersion("v3.1", "TLS")
        self.assertTrue(v1 == v2)

    def test_cmp6(self):
        v1 = SIPpVersion(None, "TLS")
        v2 = SIPpVersion(None, "TLS")
        self.assertTrue(v1 == v2)

    def test_cmp7(self):
        v1 = SIPpVersion("v2.0.1", None)
        v2 = SIPpVersion("v2.0.1", None)
        self.assertTrue(v1 == v2)

    def test_cmp8(self):
        v1 = SIPpVersion("v3.2", "TLS")
        v2 = SIPpVersion("v3.2", "PCAP")
        self.assertTrue(v1 != v2)

    def test_cmp9(self):
        v1 = SIPpVersion(None, "TLS")
        v2 = SIPpVersion(None, "PCAP")
        self.assertTrue(v1 != v2)

    def test_cmp10(self):
        v1 = SIPpVersion("v3.2", "TLS")
        v2 = SIPpVersion("v3.2", "PCAP")
        self.assertFalse(v1 == v2)

    def test_cmp11(self):
        v1 = SIPpVersion(None, "TLS")
        v2 = SIPpVersion(None, "PCAP")
        self.assertFalse(v1 == v2)

    def test_cmp12(self):
        v1 = SIPpVersion("v3.2", "TLS-PCAP")
        v2 = SIPpVersion("v3.2", "TLS")
        self.assertTrue(v1 >= v2)

    def test_cmp13(self):
        v1 = SIPpVersion("v3.2", "TLS-PCAP")
        v2 = SIPpVersion(None, "TLS")
        self.assertTrue(v1 >= v2)

    def test_cmp14(self):
        v1 = SIPpVersion("v3.2", "TLS-PCAP")
        v2 = SIPpVersion("v3.2", "PCAP")
        self.assertTrue(v1 >= v2)

    def test_cmp15(self):
        v1 = SIPpVersion("v3.2", "TLS-PCAP")
        v2 = SIPpVersion(None, "PCAP")
        self.assertTrue(v1 >= v2)

    def test_cmp16(self):
        v1 = SIPpVersion("v3.2", "TLS-PCAP")
        v2 = SIPpVersion("v3.2", "TLS")
        self.assertTrue(v1 != v2)

    def test_cmp17(self):
        v1 = SIPpVersion("v3.2", "TLS-PCAP")
        v2 = SIPpVersion(None, "TLS")
        self.assertTrue(v1 != v2)

    def test_cmp18(self):
        v1 = SIPpVersion("v3.2", "TLS-PCAP")
        v2 = SIPpVersion("v3.2", "TLS")
        self.assertFalse(v1 == v2)

    def test_cmp19(self):
        v1 = SIPpVersion("v3.2", "TLS-PCAP")
        v2 = SIPpVersion(None, "TLS")
        self.assertFalse(v1 == v2)

    def test_cmp20(self):
        v1 = SIPpVersion("v3.1", "PCAP")
        v2 = SIPpVersion("v3.0", "TLS")
        self.assertTrue(v1 > v2)

    def test_cmp21(self):
        v1 = SIPpVersion("v3.2", "TLS-PCAP")
        v2 = SIPpVersion("v2.0.1", "PCAP")
        self.assertTrue(v1 >= v2)

    def test_cmp22(self):
        v1 = SIPpVersion("v3.1", "TLS")
        v2 = SIPpVersion("v3.1", "PCAP")
        self.assertFalse(v1 > v2)

    def test_cmp23(self):
        v1 = SIPpVersion("v3.1", "TLS")
        v2 = SIPpVersion("v3.1", "PCAP")
        self.assertFalse(v1 < v2)

    def test_cmp24(self):
        v1 = SIPpVersion("v3.2", "TLS")
        v2 = SIPpVersion("v3.1", "TLS-PCAP")
        self.assertTrue(v1 >= v2)

    def test_cmp25(self):
        v1 = SIPpVersion("v3.1", "TLS-PCAP")
        v2 = SIPpVersion("v3.2", "PCAP")
        self.assertTrue(v1 <= v2)

    def test_cmp26(self):
        v1 = SIPpVersion("v2.0.1", "TLS-PCAP")
        v2 = SIPpVersion("v3.0", "TLS")
        self.assertFalse(v1 >= v2)


if __name__ == "__main__":
    main()
