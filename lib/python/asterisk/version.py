#!/usr/bin/env python
'''
Copyright (C) 2010, Digium, Inc.
Russell Bryant <russell@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
'''

import sys
import re
import unittest


VERSION_HDR = "../include/asterisk/version.h"


class AsteriskVersion:
    def __init__(self, version=None, path=VERSION_HDR):
        if version is not None:
            self.version_str = version
        else:
            self.version_str = self.__get_ast_version(path)

        if self.version_str[:3] == "SVN":
            self.__parse_svn_version()
        else:
            self.__parse_version()

    def __str__(self):
        return self.version_str

    def __int__(self):
        if self.svn is True:
            if self.branch == "trunk":
                return 99999999
            elif self.branch[:6] == "branch":
                return int(AsteriskVersion(self.branch[7:])) + 99
            else:
                # team branch XXX (may not be off of trunk)
                return 99999999
        else:
            res = int(self.concept) * 10000000 + int(self.major) * 100000
            if self.minor is not None:
                res += int(self.minor) * 1000
                if self.patch is not None:
                    res += int(self.patch) * 10
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
        self.major = parts[1]
        self.minor = None
        self.patch = None
        if len(parts) >= 3:
            self.minor = parts[2]
        if len(parts) >= 4:
            self.patch = parts[3]

    def __parse_svn_version(self):
        self.svn = True
        match = re.search(
                "SVN-(?P<branch>.*)-r(?P<revision>\d+M?)(?:-(?P<parent>.*))?",
                self.version_str
        )
        if match is not None:
            self.branch = match.group("branch")
            self.revision = match.group("revision")
            self.parent = match.group("parent")

    def __get_ast_version(self, path):
        '''
        Determine the version of Asterisk installed from the installed version.h.
        '''
        v = ""
        try:
            f = open(path, "r")
            match = re.search("ASTERISK_VERSION\s+\"(.*)\"", f.read())
            if match is not None:
                v = match.group(1)
            f.close()
        except IOError:
            print "I/O Error getting Asterisk version from %s" % path
        except:
            print "Unexpected error getting version from %s: %s" % (path,
                    sys.exc_info()[0])
        return v


class AsteriskVersionTests(unittest.TestCase):
    def test_version(self):
        v = AsteriskVersion("1.4.30")
        self.assertFalse(v.svn)
        self.assertEqual(str(v), "1.4.30")
        self.assertEqual(v.concept, "1")
        self.assertEqual(v.major, "4")
        self.assertEqual(v.minor, "30")

    def test_version2(self):
        v = AsteriskVersion("1.4.30.1")
        self.assertFalse(v.svn)
        self.assertEqual(str(v), "1.4.30.1")
        self.assertEqual(v.concept, "1")
        self.assertEqual(v.major, "4")
        self.assertEqual(v.minor, "30")
        self.assertEqual(v.patch, "1")

    def test_version3(self):
        v = AsteriskVersion("1.4")
        self.assertFalse(v.svn)
        self.assertEqual(str(v), "1.4")
        self.assertEqual(v.concept, "1")
        self.assertEqual(v.major, "4")

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


def main():
    unittest.main()


if __name__ == "__main__":
    main()
