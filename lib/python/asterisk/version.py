#!/usr/bin/env python

"""Asterisk Version String Handling

This module implements an Asterisk version string parser.  It can also compare
version strings to determine which version is considered newer.

Copyright (C) 2010, Digium, Inc.
Russell Bryant <russell@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
"""

import re
import unittest
import logging
import subprocess

import TestSuiteUtils

logger = logging.getLogger(__name__)

class AsteriskVersion:
    """An Asterisk Version.

    This class handles Asterisk version strings.
    """
    def __init__(self, version=None):
        """Construct an Asterisk Version parser.

        Keyword Arguments:
        version -- The Asterisk version string to parse.
        """
        self.svn = False
        self.phone = None

        if version is not None:
            self.version_str = version
        else:
            self.version_str = self.get_asterisk_version_from_binary()

        if self.version_str[:3] == "SVN":
            self.__parse_svn_version()
        else:
            self.__parse_version()

    def __str__(self):
        return self.version_str

    def __int__(self):
        if self.svn is True:
            if self.branch == "trunk":
                res = 9999999999
            elif self.branch[:6] == "branch":
                res = int(AsteriskVersion(self.branch[7:])) + 999999
            else:
                # team branch XXX (may not be off of trunk)
                res = 9999999999
        else:
            res = int(self.concept) * 100000000
            if self.major is not None:
                res += int(self.major) * 1000000
                if self.minor is not None:
                    res += int(self.minor) * 10000
                    if self.patch is not None:
                        if isinstance(self.patch, (int, long)):
                            res += self.patch
                        else:
                            res += int(self.__parse_version_patch(self.patch))
        return res

    def __cmp__(self, other):
        res = cmp(int(self), int(other))
        if res == 0 and self.svn and other.svn:
            res = cmp(int(self.revision.split("M")[0]),
                      int(other.revision.split("M")[0]))
        return res

    def __parse_version(self):
        self.svn = False
        parts = self.version_str.split(".")
        self.concept = parts[0]
        self.major = None
        self.minor = None
        self.patch = None
        self.branch = self.__parse_version_branch("branch-%s" % self.concept)

        if len(parts) >= 2:
            self.major = parts[1]
        if len(parts) >= 3:
            self.minor = parts[2]
            if "-" in self.minor:
                self.patch = self.__parse_version_patch(self.minor)
                self.minor = self.minor[:self.minor.find("-")]
        if len(parts) >= 4:
            self.patch = parts[3]

        if int(self.concept) == 1:
            self.branch += ".%s" % self.major
            if int(self.major) == 6:
                self.branch += ".%s" % self.minor

    def __parse_svn_version(self):
        self.svn = True
        match = re.search(
                "SVN-(?P<branch>.*)-r(?P<revision>\d+M?)(?:-(?P<parent>.*))?",
                self.version_str
        )
        if match is not None:
            self.branch = self.__parse_version_branch(match.group("branch"))
            self.revision = match.group("revision")
            self.parent = match.group("parent")

    def __parse_version_branch(self, branch):
        self.phone = '-digiumphones' in branch
        return branch.replace("-digiumphones", "")

    def __parse_version_patch(self, patch):
        parts = patch.split("-")
        ret = int(parts[0])
        if len(parts) >= 2:
            versions = [
                ["rc", 100],
                ["beta", 10],
                ["cert", 1000]
            ]
            for v, cost in versions:
                match = re.search(
                    "%s(?P<%s>.*)" % (v, v),
                    patch
                )
                if match is not None:
                    ret = int(match.group("%s" % v)) + cost
                    continue
        else:
            ret = ret + 1000

        return ret

    def is_same_branch(self, version):
        if (version.branch == self.branch) and (version.phone == self.phone):
            return True

    @classmethod
    def get_asterisk_version_from_binary(cls):
        """
        Obtain the version from Asterisk and return (a cached version of) it
        """
        if not hasattr(cls, "_asterisk_version_from_binary"):
            version = ""
            ast_binary = TestSuiteUtils.which("asterisk") or "/usr/sbin/asterisk"
            cmd = [
                ast_binary,
                "-V",
            ]

            try:
                process = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                        stderr=None)
                version = process.stdout.read()
            except OSError as oe:
                logger.error("OSError [%d]: %s" % (oe.errno, oe.strerror))
                raise

            cls._asterisk_version_from_binary = version.replace("Asterisk ", "")
        return cls._asterisk_version_from_binary


class AsteriskVersionTests(unittest.TestCase):
    def test_version(self):
        v = AsteriskVersion("1.4.30")
        self.assertFalse(v.svn)
        self.assertEqual(str(v), "1.4.30")
        self.assertEqual(v.concept, "1")
        self.assertEqual(v.major, "4")
        self.assertEqual(v.minor, "30")
        self.assertEqual(v.branch, "branch-1.4")

    def test_version2(self):
        v = AsteriskVersion("1.4.30.1")
        self.assertFalse(v.svn)
        self.assertEqual(str(v), "1.4.30.1")
        self.assertEqual(v.concept, "1")
        self.assertEqual(v.major, "4")
        self.assertEqual(v.minor, "30")
        self.assertEqual(v.patch, "1")
        self.assertEqual(v.branch, "branch-1.4")

    def test_version3(self):
        v = AsteriskVersion("1.6.2")
        self.assertFalse(v.svn)
        self.assertEqual(str(v), "1.6.2")
        self.assertEqual(v.concept, "1")
        self.assertEqual(v.major, "6")
        self.assertEqual(v.minor, "2")
        self.assertEqual(v.branch, "branch-1.6.2")

    def test_version4(self):
        v = AsteriskVersion("1.8.6.0")
        self.assertFalse(v.svn)
        self.assertEqual(str(v), "1.8.6.0")
        self.assertEqual(v.concept, "1")
        self.assertEqual(v.major, "8")
        self.assertEqual(v.minor, "6")
        self.assertEqual(v.patch, "0")
        self.assertEqual(v.branch, "branch-1.8")

    def test_version5(self):
        v = AsteriskVersion("10.0")
        self.assertFalse(v.svn)
        self.assertEqual(str(v), "10.0")
        self.assertEqual(v.concept, "10")
        self.assertEqual(v.major, "0")
        self.assertEqual(v.branch, "branch-10")

    def test_version6(self):
        v = AsteriskVersion("10")
        self.assertFalse(v.svn)
        self.assertEqual(str(v), "10")
        self.assertEqual(v.concept, "10")
        self.assertEqual(v.branch, "branch-10")

    def test_svn_version(self):
        v = AsteriskVersion("SVN-trunk-r252849")
        self.assertTrue(v.svn)
        self.assertEqual(str(v), "SVN-trunk-r252849")
        self.assertEqual(v.branch, "trunk")
        self.assertEqual(v.revision, "252849")

    def test_svn_version2(self):
        v = AsteriskVersion("SVN-branch-1.6.2-r245581M")
        self.assertTrue(v.svn)
        self.assertEqual(str(v), "SVN-branch-1.6.2-r245581M")
        self.assertEqual(v.branch, "branch-1.6.2")
        self.assertEqual(v.revision, "245581M")

    def test_svn_version3(self):
        v = AsteriskVersion("SVN-russell-cdr-q-r249059M-/trunk")
        self.assertTrue(v.svn)
        self.assertEqual(str(v), "SVN-russell-cdr-q-r249059M-/trunk")
        self.assertEqual(v.branch, "russell-cdr-q")
        self.assertEqual(v.revision, "249059M")
        self.assertEqual(v.parent, "/trunk")

    def test_svn_version4(self):
        v = AsteriskVersion("SVN-russell-rest-r12345")
        self.assertTrue(v.svn)
        self.assertEqual(str(v), "SVN-russell-rest-r12345")
        self.assertEqual(v.branch, "russell-rest")
        self.assertEqual(v.revision, "12345")

    def test_svn_version5(self):
        v = AsteriskVersion("SVN-branch-10-r12345")
        self.assertTrue(v.svn)
        self.assertEqual(str(v), "SVN-branch-10-r12345")
        self.assertEqual(v.branch, "branch-10")
        self.assertEqual(v.revision, "12345")
        self.assertFalse(v.phone)

    def test_svn_version6(self):
        v = AsteriskVersion("SVN-branch-1.8-digiumphones-r357808-/branches/1.8")
        self.assertTrue(v.svn)
        self.assertEqual(v.branch, "branch-1.8")
        self.assertEqual(v.revision, "357808")
        self.assertEqual(v.parent, "/branches/1.8")
        self.assertTrue(v.phone)

    def test_svn_version7(self):
        v = AsteriskVersion("SVN-branch-10-digiumphones-r365402-/branches/10")
        self.assertTrue(v.svn)
        self.assertEqual(v.branch, "branch-10")
        self.assertEqual(v.revision, "365402")
        self.assertEqual(v.parent, "/branches/10")
        self.assertTrue(v.phone)

    def test_svn_version8(self):
        v = AsteriskVersion("1.8.11-cert1")
        self.assertFalse(v.svn)
        self.assertEqual(str(v), "1.8.11-cert1")
        self.assertEqual(v.concept, "1")
        self.assertEqual(v.major, "8")
        self.assertEqual(v.minor, "11")
        self.assertEqual(v.patch, 1001)

    def test_svn_version9(self):
        v = AsteriskVersion("1.8.11-cert2")
        self.assertFalse(v.svn)
        self.assertEqual(str(v), "1.8.11-cert2")
        self.assertEqual(v.concept, "1")
        self.assertEqual(v.major, "8")
        self.assertEqual(v.minor, "11")
        self.assertEqual(v.patch, 1002)

    def test_cmp(self):
        v1 = AsteriskVersion("1.4")
        v2 = AsteriskVersion("1.6.0")
        self.assertTrue(v1 < v2)

    def test_cmp2(self):
        v1 = AsteriskVersion("1.4")
        v2 = AsteriskVersion("1.4.15")
        self.assertTrue(v1 < v2)

    def test_cmp3(self):
        v1 = AsteriskVersion("1.4.30")
        v2 = AsteriskVersion("1.4.30.1")
        self.assertTrue(v1 < v2)

    def test_cmp4(self):
        v1 = AsteriskVersion("1.4")
        v2 = AsteriskVersion("1.4")
        self.assertTrue(v1 == v2)

    def test_cmp5(self):
        v1 = AsteriskVersion("1.6.0")
        v2 = AsteriskVersion("1.6.0")
        self.assertTrue(v1 == v2)

    def test_cmp6(self):
        v1 = AsteriskVersion("1.6.0.10")
        v2 = AsteriskVersion("1.6.0.10")
        self.assertTrue(v1 == v2)

    def test_cmp7(self):
        v1 = AsteriskVersion("1.8")
        v2 = AsteriskVersion("2.0")
        self.assertTrue(v1 < v2)

    def test_cmp8(self):
        v1 = AsteriskVersion("SVN-trunk-r252849")
        v2 = AsteriskVersion("SVN-branch-1.6.2-r245581M")
        self.assertTrue(v1 > v2)

    def test_cmp9(self):
        v1 = AsteriskVersion("SVN-trunk-r252849")
        v2 = AsteriskVersion("SVN-trunk-r252850M")
        self.assertTrue(v1 < v2)

    def test_cmp10(self):
        v1 = AsteriskVersion("SVN-trunk-r252849")
        v2 = AsteriskVersion("SVN-russell-cdr-q-r249059M-/trunk")
        self.assertTrue(v1 > v2)

    def test_cmp11(self):
        v1 = AsteriskVersion("SVN-branch-1.6.2-r245581M")
        v2 = AsteriskVersion("SVN-branch-1.6.1-r245581M")
        self.assertTrue(v1 > v2)

    def test_cmp12(self):
        v1 = AsteriskVersion("SVN-branch-10-r245581M")
        v2 = AsteriskVersion("SVN-branch-1.6.1-r245581M")
        self.assertTrue(v1 > v2)

    def test_cmp13(self):
        v1 = AsteriskVersion("10.0")
        v2 = AsteriskVersion("1.8")
        self.assertTrue(v1 > v2)

    def test_cmp14(self):
        v1 = AsteriskVersion("10")
        v2 = AsteriskVersion("1.8")
        self.assertTrue(v1 > v2)

    def test_cmp15(self):
        v1 = AsteriskVersion("SVN-trunk-r245581")
        v2 = AsteriskVersion("SVN-branch-10-r251232")
        self.assertTrue(v1 > v2)

    def test_cmp16(self):
        v1 = AsteriskVersion("1.8.6.0-rc1")
        v2 = AsteriskVersion("1.8.6.0")
        self.assertTrue(v1 < v2)

    def test_cmp17(self):
        v1 = AsteriskVersion("1.8.8.0-beta1")
        v2 = AsteriskVersion("1.8.8.0-rc1")
        self.assertTrue(v1 < v2)

    def test_cmp18(self):
        v1 = AsteriskVersion("1.8.6.0-rc2")
        v2 = AsteriskVersion("1.8.6.0-rc1")
        self.assertTrue(v1 > v2)

    def test_cmp19(self):
        v1 = AsteriskVersion("1.8.6.1")
        v2 = AsteriskVersion("1.8.6.0-rc11")
        self.assertTrue(v1 > v2)

    def test_cmp20(self):
        v1 = AsteriskVersion("1.8.5.0")
        v2 = AsteriskVersion("1.8.5.1")
        self.assertTrue(v1 < v2)

    def test_cmp21(self):
        v1 = AsteriskVersion("1.8.10")
        v2 = AsteriskVersion("SVN-branch-1.8-r360138")
        self.assertTrue(v1 < v2)

    def test_cmp22(self):
        v1 = AsteriskVersion("1.8.10")
        v2 = AsteriskVersion("SVN-branch-1.8-r360138M")
        self.assertTrue(v1 < v2)

    def test_cmp23(self):
        v1 = AsteriskVersion("1.8.11-cert1")
        v2 = AsteriskVersion("1.8.11-cert2")
        self.assertTrue(v1 < v2)

    def test_cmp24(self):
        v1 = AsteriskVersion("1.8.11-cert1")
        v2 = AsteriskVersion("1.8.15-cert1")
        self.assertTrue(v1 < v2)

def main():
    unittest.main()


if __name__ == "__main__":
    main()
