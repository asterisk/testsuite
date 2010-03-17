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

class AsteriskVersion:
    def __init__(self, version=None):
        if version is not None:
            self.version_str = version
        else:
            self.version_str = self.__get_ast_version()

        if self.version_str[:3] == "SVN":
            self.__parse_svn_version()
        else:
            self.__parse_version()

    def __str__(self):
        return self.version_str

    def __parse_version(self):
        self.svn = False
        parts = self.version_str.split(".")
        self.concept = parts[0]
        self.major = parts[1]
        self.minor = parts[2]
        if len(parts) > 3:
            self.patch = parts[3]

    def __parse_svn_version(self):
        self.svn = True
        match = re.search("SVN-(.*)-r(.*)", self.version_str)
        if match is not None:
            self.branch = match.group(1)
            self.revision = match.group(2)
            # I know you could do this with one regex.  If someone wants
            # to help me figure out why I couldn't do it, that would rock.
            match = re.search("(.*)-(.*)", self.revision)
            if match is not None:
                self.revision = match.group(1)
                self.parent = match.group(2)

    def __get_ast_version(self):
        '''
        Determine the version of Asterisk installed from the installed version.h.
        '''
        v = ""
        try:
            f = open(VERSION_HDR, "r")
        except:
            print "Failed to open %s to get Asterisk version." % VERSION_HDR
            return v

        match = re.search("ASTERISK_VERSION\s+\"(.*)\"", f.read())
        if match is not None:
            v = match.group(1)

        f.close()

        return v


class AsteriskVersionTests(unittest.TestCase):
    def test_version(self):
        '''
        Test normal version strings.
        '''
        v1 = AsteriskVersion("1.4.30")
        self.assertFalse(v1.svn)
        self.assertEqual(str(v1), "1.4.30")
        self.assertEqual(v1.concept, "1")
        self.assertEqual(v1.major, "4")
        self.assertEqual(v1.minor, "30")

        v2 = AsteriskVersion("1.4.30.1")
        self.assertFalse(v2.svn)
        self.assertEqual(str(v2), "1.4.30.1")
        self.assertEqual(v2.concept, "1")
        self.assertEqual(v2.major, "4")
        self.assertEqual(v2.minor, "30")
        self.assertEqual(v2.patch, "1")

    def test_svn_version(self):
        '''
        Test SVN version strings.
        '''
        v3 = AsteriskVersion("SVN-trunk-r252849")
        self.assertTrue(v3.svn)
        self.assertEqual(str(v3), "SVN-trunk-r252849")
        self.assertEqual(v3.branch, "trunk")
        self.assertEqual(v3.revision, "252849")

        v4 = AsteriskVersion("SVN-branch-1.6.2-r245581M")
        self.assertTrue(v4.svn)
        self.assertEqual(str(v4), "SVN-branch-1.6.2-r245581M")
        self.assertEqual(v4.branch, "branch-1.6.2")
        self.assertEqual(v4.revision, "245581M")

        v5 = AsteriskVersion("SVN-russell-cdr-q-r249059M-/trunk")
        self.assertTrue(v5.svn)
        self.assertEqual(str(v5), "SVN-russell-cdr-q-r249059M-/trunk")
        self.assertEqual(v5.branch, "russell-cdr-q")
        self.assertEqual(v5.revision, "249059M")
        self.assertEqual(v5.parent, "/trunk")


def main():
    unittest.main()


if __name__ == "__main__":
    main()
