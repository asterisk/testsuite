#!/usr/bin/env python
"""SIPp Version String Handling

Copyright (C) 2010, Digium, Inc.
Paul Belanger <pabelanger@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
"""

import subprocess
import sys
import unittest
sys.path.append("lib/python")

import test_suite_utils

class SIPpVersion:
    """A SIPp Version.

    """
    def __init__(self, version=None, feature=None):
        """Construct a SIPp Version parser.

        Keyword Arguments:
        version The SIPp version string to parse.
        """
        self.version_str = None
        self.feature_str = None
        self.concept = None
        self.major = None
        self.minor = None
        self.tls = False
        self.pcap = False

        if version is None and feature is None:
            sipp = test_suite_utils.which("sipp")
            if sipp is None:
               return

            cmd = [
                sipp, "-v"
            ]
            try:
                sipp_process = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT)
            except OSError:
                return
            for line in sipp_process.stdout:
                if line.strip().startswith('SIPp'):
                    sipp = line.strip().lstrip('SIPp ')
                    sipp = sipp.split(',', 1)
                    sipp = sipp[0].split('-', 1)
                    version = sipp[0]
                    if len(sipp) > 1:
                        feature = sipp[1]
            sipp_process.wait()

        if version is not None:
            self.__parse_version(version)
        if feature is not None:
            self.__parse_feature(feature)

    def __str__(self):
        """String representation of the SIPp version"""
        res = ''
        if self.version_str is not None:
            res = self.version_str
        if self.feature_str is not None:
            res = "%s-%s" % (res, self.feature_str)

        return res.strip('-')

    def __int__(self):
        """Return the version as an integer value

        This allows for comparisons between SIPp versions"""
        res = 0
        if self.concept is not None:
            res = int(self.concept.strip('v')) * 10000000
        if self.major is not None:
            res += int(self.major) * 100000
        if self.minor is not None:
            res += int(self.minor) * 1000

        return res

    def __cmp__(self, other):
        """Compare two SIPpVersion instances against each other"""
        return cmp(int(self), int(other))

    def __ne__(self, other):
        """Determine if this SIPpVersion instance is not equal to another"""
        res = self.__cmp__(other)
        if ((res == 0) and (self.tls or self.pcap or other.tls or other.pcap)):
            if (self.tls == other.pcap) or (self.pcap == other.tls):
                return True
            return False
        return res

    def __eq__(self, other):
        """Determine if this SIPpVersion instance is equal to another"""
        res = self.__cmp__(other)
        if ((res == 0) and (self.tls == other.tls and self.pcap == other.pcap)):
                return True
        return False

    def __parse_version(self, version):
        """Parse the version string returned from SIPp"""
        self.version_str = version
        if version is not None:
            parts = self.version_str.split(".")
            self.concept = parts[0]
            self.major = parts[1]
            self.minor = None
            if len(parts) >= 3:
                self.minor = parts[2]

    def __parse_feature(self, value):
        """Parse the features supported by this SIPp install"""
        self.feature_str = value
        if value.find("TLS") > -1:
            self.tls = True
        if value.find("PCAP") > -1:
            self.pcap = True

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


def main():
    unittest.main()


if __name__ == "__main__":
    main()
