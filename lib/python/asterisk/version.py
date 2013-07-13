#!/usr/bin/env python

"""Asterisk Version String Handling

This module implements an Asterisk version string parser.  It can also compare
version strings to determine which version is considered newer.

Copyright (C) 2012, Digium, Inc.
Russell Bryant <russell@digium.com>
Matt Jordan <mjordan@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
"""

import re
import unittest
import logging
import sys
import subprocess

import TestSuiteUtils

logger = logging.getLogger(__name__)

class AsteriskVersion:
    """An Asterisk Version.

    This class handles Asterisk version strings.
    """

    supported_features = [ 'cert', 'digiumphones', 'dfsg' ]

    supported_modifiers = [ 'rc', 'beta' ]

    def __init__(self, version=None):
        """Construct an Asterisk Version parser.

        Keyword Arguments:
        version -- The Asterisk version string to parse.
        """

        if not version:
            version = AsteriskVersion.get_asterisk_version_from_binary()

        self.raw_version = version

        (self.major,
         self.minor,
         self.patch,
         self.iteration,
         self.revision,
         self.branch,
         self.svn,
         self.name,
         self.feature,
         self.modifier,
         self.parent) = self._parse_version_string(self.raw_version)

    def __str__(self):
        return self.raw_version

    def __int__(self):
        if self.name:
            return sys.maxint
        elif (self.branch):
            # Branches are a little odd.  The more you specify, the less your calculated
            # value is.  This keeps the following relationships true:
            # branch-1.8 > 1.8.12.0 > branch-1.8.11-cert
            value = self.major * 100000000
            if (self.minor == 0):
                value += 9900000
            else:
                value += self.minor * 100000
            if (self.patch == 0):
                value += 99000
            else:
                value += self.patch * 1000
            value += 999
            return value
        else:
            return self._modifier_weight() + self.patch * 1000 + self.minor * 100000 + self.major * 100000000

    def __cmp__(self, other):
        self_value = int(self)
        other_value = int(other)
        res = cmp(int(self), int(other))
        if res == 0:
            if self.svn and other.svn:
                res = cmp(self.revision, other.revision)

        return res

    def _parse_version_string(self, raw_version):
        branch = False
        svn = False
        feature = ''
        parsed_numbers = [0, 0, 0]
        name = ''
        revision = 0
        parent = ''
        iteration = 0
        modifier = ''

        raw_version = raw_version.replace('Asterisk ', '')

        tokens = re.split('[-~]', raw_version)
        count = 0
        while (count < len(tokens)):
            token = tokens[count]
            # Determine if we're a subversion branch
            if 'SVN' == token:
                svn = True
            elif 'branch' == token:
                branch = True
            else:
                if svn and not branch and not name:
                    # Team branch or trunk.  This will modify the current position
                    # based on the number of tokens consumed
                    (name, munched) = self._parse_branch_name(tokens[count:])
                    count += munched
                else:
                    handled = False
                    if (len([num for num in parsed_numbers if num != 0]) == 0):
                        (parsed_numbers, handled) = self._parse_version(token)
                    if not handled and revision == 0:
                        (revision, handled) = self._parse_revision(token)
                    if not handled and not feature:
                        # If a feature returns back a number, its actually the 'patch' version
                        # number (e.g., 1.8.11-cert3)
                        (feature, temp, handled) = self._parse_feature(token)
                        if (temp > 0):
                            parsed_numbers[2] = temp
                    if not handled and not modifier:
                        (modifier, iteration, handled) = self._parse_version_modifier(token)
                    if not handled and not parent:
                        (parent, handled) = self._parse_parent_branch(token)
                    if not handled:
                        logger.error("Unable to parse token '%s' in version string '%s'" %
                                     (token, raw_version))
            count += 1
        return (parsed_numbers[0], parsed_numbers[1], parsed_numbers[2], iteration,
                revision, branch, svn, name, feature, modifier, parent)

    def _parse_branch_name(self, branch_tokens):
        name = branch_tokens[0]
        munched = 0
        for i in range(1, len(branch_tokens)):
            # Stop when we hit the revision
            if branch_tokens[i][0] == 'r':
                candidate = branch_tokens[i].replace('r','').replace('M','').replace('m','')
                if candidate.isdigit():
                    break
            name += '-' + branch_tokens[i]
            munched += 1
        return (name, munched)

    def _parse_version(self, version_string):
        parsed_numbers = [0,0,0]
        version_tokens = version_string.split('.')
        count = 0
        if not version_tokens[0].isdigit():
            return (parsed_numbers, False)
        for token in version_tokens:
            if count == 0 and int(token) == 1:
                # Skip '1' in '1.8' branches - it adds no value
                continue
            parsed_numbers[count] = int(token)
            count += 1
        return (parsed_numbers, True)

    def _parse_revision(self, revision_string):
        candidate = revision_string.replace('M', '').replace('r','').replace('m','')
        if candidate.isdigit():
            return (int(candidate), True)
        return (0, False)

    def _parse_feature(self, feature_string):
        for f in AsteriskVersion.supported_features:
            if f in feature_string:
                feature_string = feature_string.replace(f, '')
                iteration = -1
                if (len(feature_string) > 0):
                    iteration = int(feature_string)
                return (f, iteration, True)
        return ('', -1, False)

    def _parse_version_modifier(self, version_modifier):
        for m in AsteriskVersion.supported_modifiers:
            if m in version_modifier:
                version_modifier = version_modifier.replace(m, '')
                iteration = -1
                if (len(version_modifier) > 0):
                    iteration = int(version_modifier)
                return (m, iteration, True)
        return ('', -1, False)

    def _parse_parent_branch(self, parent_branch):
        # Parent branch can be just about anything, so just accept it.
        # This should be the last thing called.
        return (parent_branch, True)

    def _modifier_weight(self):
        if self.modifier:
            if self.modifier == 'rc':
                return self.iteration * 10
            else:
                return self.iteration
        return 100

    def has_feature(self, feature):
        if (self.name or self.major >= 11):
            # Assume that 11 or trunk has all the features
            return True
        if feature == self.feature:
            return True
        else:
            if feature == 'digiumphones' and self.feature == 'cert':
                return True
        return False

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

    def test_version_18_1(self):
        v = AsteriskVersion("1.8.6.0")
        self.assertFalse(v.svn)
        self.assertFalse(v.branch)
        self.assertEqual(str(v), "1.8.6.0")
        self.assertEqual(v.major, 8)
        self.assertEqual(v.minor, 6)
        self.assertEqual(v.patch, 0)

    def test_version_18_2(self):
        v = AsteriskVersion("Asterisk 1.8.13.1")
        self.assertFalse(v.svn)
        self.assertFalse(v.branch)
        self.assertEqual(str(v), "Asterisk 1.8.13.1")
        self.assertEqual(v.major, 8)
        self.assertEqual(v.minor, 13)
        self.assertEqual(v.patch, 1)

    def test_version_10_1(self):
        v = AsteriskVersion("10.0")
        self.assertFalse(v.svn)
        self.assertFalse(v.branch)
        self.assertEqual(str(v), "10.0")
        self.assertEqual(v.major, 10)
        self.assertEqual(v.minor, 0)
        self.assertEqual(v.patch, 0)

    def test_version_10_2(self):
        v = AsteriskVersion("Asterisk 10.5.1")
        self.assertFalse(v.svn)
        self.assertFalse(v.branch)
        self.assertEqual(str(v), "Asterisk 10.5.1")
        self.assertEqual(v.major, 10)
        self.assertEqual(v.minor, 5)
        self.assertEqual(v.patch, 1)

    def test_version_11_1(self):
        v = AsteriskVersion("11")
        self.assertFalse(v.svn)
        self.assertFalse(v.branch)
        self.assertEqual(str(v), "11")
        self.assertEqual(v.major, 11)
        self.assertEqual(v.minor, 0)
        self.assertEqual(v.patch, 0)

    def test_version_11_2(self):
        v = AsteriskVersion("11.1.9")
        self.assertFalse(v.svn)
        self.assertFalse(v.branch)
        self.assertEqual(str(v), "11.1.9")
        self.assertEqual(v.major, 11)
        self.assertEqual(v.minor, 1)
        self.assertEqual(v.patch, 9)

    def test_version_11_3(self):
        v = AsteriskVersion("Asterisk 11.0")
        self.assertFalse(v.svn)
        self.assertFalse(v.branch)
        self.assertEqual(str(v), "Asterisk 11.0")
        self.assertEqual(v.major, 11)
        self.assertEqual(v.minor, 0)
        self.assertEqual(v.patch, 0)

    def test_svn_version_trunk_1(self):
        v = AsteriskVersion("SVN-trunk-r252849")
        self.assertTrue(v.svn)
        self.assertFalse(v.branch)
        self.assertEqual(str(v), "SVN-trunk-r252849")
        self.assertEqual(v.name, "trunk")
        self.assertEqual(v.revision, 252849)

    def test_svn_version_trunk_2(self):
        v = AsteriskVersion("Asterisk SVN-trunk-r252849M")
        self.assertTrue(v.svn)
        self.assertFalse(v.branch)
        self.assertEqual(str(v), "Asterisk SVN-trunk-r252849M")
        self.assertEqual(v.name, "trunk")
        self.assertEqual(v.revision, 252849)

    def test_svn_version_teambranch_1(self):
        v = AsteriskVersion("SVN-russell-cdr-q-r249059M-/trunk")
        self.assertTrue(v.svn)
        self.assertFalse(v.branch)
        self.assertEqual(str(v), "SVN-russell-cdr-q-r249059M-/trunk")
        self.assertEqual(v.name, "russell-cdr-q")
        self.assertEqual(v.revision, 249059)
        self.assertEqual(v.parent, "/trunk")

    def test_svn_version_teambranch_2(self):
        v = AsteriskVersion("Asterisk SVN-russell-rest-r12345")
        self.assertTrue(v.svn)
        self.assertFalse(v.branch)
        self.assertEqual(str(v), "Asterisk SVN-russell-rest-r12345")
        self.assertEqual(v.name, "russell-rest")
        self.assertEqual(v.revision, 12345)

    def test_svn_branch_10_1(self):
        v = AsteriskVersion("SVN-branch-10-r11111")
        self.assertTrue(v.svn)
        self.assertTrue(v.branch)
        self.assertEqual(str(v), "SVN-branch-10-r11111")
        self.assertEqual(v.major, 10)
        self.assertEqual(v.minor, 0)
        self.assertEqual(v.patch, 0)
        self.assertEqual(v.revision, 11111)

    def test_svn_branch_18_features_1(self):
        v = AsteriskVersion("SVN-branch-1.8-digiumphones-r357808-/branches/1.8")
        self.assertTrue(v.svn)
        self.assertTrue(v.branch)
        self.assertEqual(v.major, 8)
        self.assertEqual(v.minor, 0)
        self.assertEqual(v.patch, 0)
        self.assertEqual(v.revision, 357808)
        self.assertEqual(v.parent, '/branches/1.8')
        self.assertTrue(v.feature, 'digiumphones')

    def test_svn_branch_10_features_1(self):
        v = AsteriskVersion("SVN-branch-10-digiumphones-r365402-/branches/10")
        self.assertTrue(v.svn)
        self.assertTrue(v.branch)
        self.assertEqual(v.major, 10)
        self.assertEqual(v.minor, 0)
        self.assertEqual(v.patch, 0)
        self.assertEqual(v.revision, 365402)
        self.assertEqual(v.parent, '/branches/10')
        self.assertEqual(v.feature, 'digiumphones')

    def test_svn_branch_10_features_2(self):
        v = AsteriskVersion("Asterisk SVN-branch-10-digiumphones-r365402")
        self.assertTrue(v.svn)
        self.assertTrue(v.branch)
        self.assertEqual(v.major, 10)
        self.assertEqual(v.minor, 0)
        self.assertEqual(v.patch, 0)
        self.assertEqual(v.revision, 365402)
        self.assertEqual(v.feature, 'digiumphones')

    def test_version_10_with_features_and_modifier(self):
        v = AsteriskVersion("Asterisk 10.6.1-digiumphones-beta3")
        self.assertFalse(v.svn)
        self.assertFalse(v.branch)
        self.assertEqual(v.major, 10)
        self.assertEqual(v.minor, 6)
        self.assertEqual(v.patch, 1)
        self.assertEqual(v.feature, 'digiumphones')
        self.assertEqual(v.modifier, 'beta')
        self.assertEqual(v.iteration, 3)

    def test_svn_1811_certified_1(self):
        v = AsteriskVersion("Asterisk 1.8.11-cert1")
        self.assertFalse(v.svn)
        self.assertFalse(v.branch)
        self.assertEqual(v.major, 8)
        self.assertEqual(v.minor, 11)
        self.assertEqual(v.patch, 1)
        self.assertEqual(v.feature, 'cert')

    def test_svn_1811_certified_2(self):
        v = AsteriskVersion("1.8.11-cert2")
        self.assertFalse(v.svn)
        self.assertFalse(v.branch)
        self.assertEqual(v.major, 8)
        self.assertEqual(v.minor, 11)
        self.assertEqual(v.patch, 2)
        self.assertEqual(v.feature, 'cert')

    def test_svn_1811_certified_3(self):
        v = AsteriskVersion("Asterisk 1.8.11-cert3-rc1")
        self.assertFalse(v.svn)
        self.assertFalse(v.branch)
        self.assertEqual(v.major, 8)
        self.assertEqual(v.minor, 11)
        self.assertEqual(v.patch, 3)
        self.assertEqual(v.feature, 'cert')
        self.assertEqual(v.modifier, 'rc')
        self.assertEqual(v.iteration, 1)

    def test_svn_1811_certified_branch(self):
        v = AsteriskVersion("Asterisk SVN-branch-1.8.11-cert-r368608")
        self.assertTrue(v.svn)
        self.assertTrue(v.branch)
        self.assertEqual(v.major, 8)
        self.assertEqual(v.minor, 11)
        self.assertEqual(v.patch, 0)
        self.assertEqual(v.feature, 'cert')
        self.assertEqual(v.revision, 368608)

    def test_cmp1(self):
        v1 = AsteriskVersion("SVN-trunk-r252849")
        v2 = AsteriskVersion("SVN-branch-1.8-r245581M")
        v3 = AsteriskVersion("Asterisk 11.0.1")
        v4 = AsteriskVersion("SVN-trunk-r300000")
        self.assertTrue(v1 > v2)
        self.assertTrue(v1 > v3)
        self.assertFalse(v1 > v4)

    def test_cmp2(self):
        v1 = AsteriskVersion("SVN-trunk-r252849")
        v2 = AsteriskVersion("SVN-russell-cdr-q-r249059M-/trunk")
        self.assertTrue(v1 > v2)

    def test_cmp3(self):
        v1 = AsteriskVersion("SVN-branch-10-r245581M")
        v2 = AsteriskVersion("SVN-branch-1.8-r245581M")
        self.assertTrue(v1 > v2)

    def test_cmp4(self):
        v1 = AsteriskVersion("10.0")
        v2 = AsteriskVersion("1.8")
        self.assertTrue(v1 > v2)

    def test_cmp5(self):
        v1 = AsteriskVersion("10")
        v2 = AsteriskVersion("1.8")
        self.assertTrue(v1 > v2)

    def test_cmp6(self):
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

    def test_cmp25(self):
        v1 = AsteriskVersion("1.8.11-cert1")
        v2 = AsteriskVersion("1.8.13.0")
        self.assertTrue(v1 < v2)

    def test_cmp26(self):
        v1 = AsteriskVersion("SVN-branch-1.8.11-cert-r363674")
        v2 = AsteriskVersion("1.8.12.0")
        self.assertTrue(v1 < v2)

    def test_cmp27(self):
        v1 = AsteriskVersion("SVN-branch-1.8.11-r363674")
        v2 = AsteriskVersion("SVN-branch-1.8.15-r363674")
        self.assertTrue(v1 < v2)

    def test_cmp28(self):
        v1 = AsteriskVersion("SVN-branch-1.8.11-r363674")
        v2 = AsteriskVersion("SVN-branch-1.8-r369138M")
        self.assertTrue(v1 < v2)

    def test_cmp29(self):
        v1 = AsteriskVersion("1.8.11-cert1")
        v2 = AsteriskVersion("Asterisk SVN-branch-1.8.11-cert-r368608")
        self.assertTrue(v1 < v2)

def main():
    unittest.main()


if __name__ == "__main__":
    main()
