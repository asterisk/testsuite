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

import test_suite_utils

LOGGER = logging.getLogger(__name__)


def parse_svn_branch_name(branch_tokens):
    """Parse an Asterisk SVN branch version"""
    name = branch_tokens[0]
    munched = 0
    for i in range(1, len(branch_tokens)):
        # Stop when we hit the revision
        if branch_tokens[i][0] == 'r':
            candidate = branch_tokens[i].replace('r', '')
            candidate = candidate.replace('M', '').replace('m', '')
            if candidate.isdigit():
                break
        name += '-' + branch_tokens[i]
        munched += 1
    return (name, munched)


def parse_version(version_string):
    """Parse a 'standard' Asterisk version"""
    parsed_numbers = [0, 0, 0]
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


def parse_revision(revision_string):
    """Parse a modified version of Asterisk"""
    candidate = revision_string.replace('M', '')
    candidate = candidate.replace('r', '').replace('m', '')
    if candidate.isdigit():
        return (int(candidate), True)
    return (0, False)


def parse_feature(feature_string):
    """Parse a feature from a version"""
    for feature in AsteriskVersion.supported_features:
        if feature in feature_string:
            feature_string = feature_string.replace(feature, '')
            iteration = -1
            if (len(feature_string) > 0):
                iteration = int(feature_string)
            return (feature, iteration, True)
    return ('', -1, False)


def parse_version_modifier(version_modifier):
    """Parse a version modifier"""
    for modifier in AsteriskVersion.supported_modifiers:
        if modifier in version_modifier:
            version_modifier = version_modifier.replace(modifier, '')
            iteration = -1
            if (len(version_modifier) > 0):
                iteration = int(version_modifier)
            return (modifier, iteration, True)
    return ('', -1, False)


def parse_parent_branch(parent_branch):
    """Parse a parent branch out of a version branch"""
    # Parent branch can be just about anything, so just accept it.
    # This should be the last thing called.
    return (parent_branch, True)


class AsteriskVersion(object):
    """An Asterisk Version.

    This class handles Asterisk version strings.

    Attributes:
    raw_version - The pre-parsed version string
    branch      - If true, this is a branch and not a tag. Note that
                  if svn is True, then this implies that we think this
                  must be 'trunk'. This is always True if git is True.
    svn         - The Asterisk version is derived from Subversion
    git         - The Asterisk version is derived from Git
    major       - The major version number
    minor       - The minor version number
    patch       - The patch version number
    feature     - Asterisk specific branch/tag features, e.g., 'cert'
    modifier    - Asterisk tag release modifiers, e.g., 'rc'
    iteration   - Iteration of the modifier, e.g., 1 for 'rc1'
    parent      - If a parent SVN branch exists, what branch this was
                  derived from
    name        - The name of the team branch or 'trunk' for SVN, or
                  'master' for Git. If None, then a major/minor/patch
                  version should be available.
    """

    supported_features = ['cert', 'digiumphones', 'dfsg']

    supported_modifiers = ['rc', 'beta']

    def __init__(self, version=None):
        """Construct an Asterisk Version parser.

        Keyword Arguments:
        version -- The Asterisk version string to parse.
        """

        if not version:
            version = AsteriskVersion.get_version_from_binary()

        self.raw_version = version
        self.branch = False
        self.svn = False
        self.git = False
        self.major = 0
        self.minor = 0
        self.patch = 0
        self.iteration = 0
        self.revision = None
        self.feature = None
        self.modifier = None
        self.parent = None
        self.name = None

        self.parse_version_string(self.raw_version)

    def parse_version_string(self, raw_version):
        """Parse a raw version string into its parts"""
        parsed_numbers = [0, 0, 0]
        raw_version = raw_version.replace('Asterisk ', '')

        tokens = re.split('[-~]', raw_version)
        count = 0
        while (count < len(tokens)):
            token = tokens[count]
            # Determine if we're a subversion branch
            if 'SVN' == token:
                self.svn = True
            elif 'GIT' == token:
                # All Git versions are branches
                self.git = True
                self.branch = True
            elif 'branch' == token:
                self.branch = True
            else:
                if self.svn and not self.branch and not self.name:
                    # Team branch or trunk.  This will modify the current
                    # position based on the number of tokens consumed
                    (self.name,
                     munched) = parse_svn_branch_name(tokens[count:])
                    count += munched
                elif self.git and token == 'master':
                    # It's a Git branch! This should contain our upstream
                    # major branch, so we only care if the current token
                    # says this is master.
                    self.name = token
                else:
                    handled = False
                    if (len([num for num in parsed_numbers if num != 0]) == 0):
                        (parsed_numbers, handled) = parse_version(token)
                        self.major = parsed_numbers[0]
                        self.minor = parsed_numbers[1]
                        self.patch = parsed_numbers[2]
                    if not handled and not self.feature:
                        # If a feature returns back a number, its actually the
                        # 'patch' version number (e.g., 1.8.11-cert3)
                        (self.feature, temp, handled) = parse_feature(token)
                        if (temp > 0):
                            self.patch = temp
                    if not handled and not self.modifier:
                        (self.modifier,
                         self.iteration,
                         handled) = parse_version_modifier(token)
                    if not handled and not self.revision:
                        if not self.git:
                            (self.revision, handled) = parse_revision(token)
                        else:
                            self.revision = token
                    if not handled and not self.parent:
                        (self.parent, handled) = parse_parent_branch(token)
                    if not handled:
                        LOGGER.error("Unable to parse token '%s' in version "
                                     "string '%s'" % (token, raw_version))
            count += 1

    def __str__(self):
        """Return the raw Asterisk version as a string"""
        return self.raw_version

    def __int__(self):
        """Convert the Asterisk version to an integer for comparisons"""
        if self.name:
            return sys.maxint
        elif (self.branch):
            # Branches are a little odd. The more you specify, the less your
            # calculated value is. This keeps the following relationships true:
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
            return (self._modifier_weight() + self.patch * 1000 +
                    self.minor * 100000 + self.major * 100000000)

    def __lt__(self, other):
        """Test if self < other """
        if int(self) < int(other):
            return True
        elif self.svn and other.svn:
            return self.revision < other.revision
        else:
            return False

    def __le__(self, other):
        """Test if self <= other"""
        if int(self) <= int(other):
            return True
        elif self.svn and other.svn:
            return self.revision <= other.revision
        else:
            return False

    def __eq__(self, other):
        """Test if self == other"""
        if int(self) != int(other):
            return False
        if (self.svn and other.svn) or (self.git and other.git):
            return self.revision == other.revision
        return True

    def __ne__(self, other):
        """Test if self != other"""
        if int(self) == int(other):
            if (self.svn and other.svn) or (self.git and other.git):
                return self.revision != other.revision
            else:
                return False
        return True

    def __gt__(self, other):
        """Test if self > other"""
        if int(self) > int(other):
            return True
        elif self.svn and other.svn:
            return self.revision > other.revision
        else:
            return False

    def __ge__(self, other):
        """Test if self >= other"""
        if int(self) >= int(other):
            return True
        elif self.svn and other.svn:
            return self.revision >= other.revision
        else:
            return False

    def _modifier_weight(self):
        """Determine the relative weight due to a modifier"""
        if self.modifier:
            if self.modifier == 'rc':
                return self.iteration * 10
            else:
                return self.iteration
        return 100

    def has_feature(self, feature):
        """Returns:
        True if this AsteriskVersion has a feature
        False otherwise
        """
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
    def get_version_from_binary(cls):
        """Obtain the version from the installed instance of Asterisk

        This method will invoke Asterisk, get the version, parse the
        result, and cache it. Once cached, the cached version will
        always be returned.

        Returns: The installed Asterisk version
        """
        if not hasattr(cls, "_asterisk_version_from_binary"):
            version = ""
            ast_binary = (test_suite_utils.which("asterisk") or
                          "/usr/sbin/asterisk")
            cmd = [
                ast_binary,
                "-V",
            ]

            try:
                process = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                           stderr=None)
                version = process.stdout.read()
            except OSError as o_excep:
                LOGGER.error("OSError [%d]: %s" % (o_excep.errno,
                                                   o_excep.strerror))
                raise
            process.wait()
            cls._asterisk_version_from_binary = version.replace(
                "Asterisk ", "")
        return cls._asterisk_version_from_binary


class AsteriskVersionTests(unittest.TestCase):
    """Unit tests for AsteriskVersion"""

    def test_version_18_1(self):
        """Test parsing 1.8 version string"""
        version = AsteriskVersion("1.8.6.0")
        self.assertFalse(version.svn)
        self.assertFalse(version.branch)
        self.assertEqual(str(version), "1.8.6.0")
        self.assertEqual(version.major, 8)
        self.assertEqual(version.minor, 6)
        self.assertEqual(version.patch, 0)

    def test_version_18_2(self):
        """Test parsing another 1.8 version string"""
        version = AsteriskVersion("Asterisk 1.8.13.1")
        self.assertFalse(version.svn)
        self.assertFalse(version.branch)
        self.assertEqual(str(version), "Asterisk 1.8.13.1")
        self.assertEqual(version.major, 8)
        self.assertEqual(version.minor, 13)
        self.assertEqual(version.patch, 1)

    def test_version_10_1(self):
        """Test parsing a 10 version string"""
        version = AsteriskVersion("10.0")
        self.assertFalse(version.svn)
        self.assertFalse(version.branch)
        self.assertEqual(str(version), "10.0")
        self.assertEqual(version.major, 10)
        self.assertEqual(version.minor, 0)
        self.assertEqual(version.patch, 0)

    def test_version_10_2(self):
        """Test parsing another 10 version string"""
        version = AsteriskVersion("Asterisk 10.5.1")
        self.assertFalse(version.svn)
        self.assertFalse(version.branch)
        self.assertEqual(str(version), "Asterisk 10.5.1")
        self.assertEqual(version.major, 10)
        self.assertEqual(version.minor, 5)
        self.assertEqual(version.patch, 1)

    def test_version_11_1(self):
        """Test parsing an 11 version string"""
        version = AsteriskVersion("11")
        self.assertFalse(version.svn)
        self.assertFalse(version.branch)
        self.assertEqual(str(version), "11")
        self.assertEqual(version.major, 11)
        self.assertEqual(version.minor, 0)
        self.assertEqual(version.patch, 0)

    def test_version_11_2(self):
        """Test parsing another 11 version string"""
        version = AsteriskVersion("11.1.9")
        self.assertFalse(version.svn)
        self.assertFalse(version.branch)
        self.assertEqual(str(version), "11.1.9")
        self.assertEqual(version.major, 11)
        self.assertEqual(version.minor, 1)
        self.assertEqual(version.patch, 9)

    def test_version_11_3(self):
        """Test parsing yet another 11 version string"""
        version = AsteriskVersion("Asterisk 11.0")
        self.assertFalse(version.svn)
        self.assertFalse(version.branch)
        self.assertEqual(str(version), "Asterisk 11.0")
        self.assertEqual(version.major, 11)
        self.assertEqual(version.minor, 0)
        self.assertEqual(version.patch, 0)

    def test_svn_version_trunk_1(self):
        """Test parsing a trunk version with revision"""
        version = AsteriskVersion("SVN-trunk-r252849")
        self.assertTrue(version.svn)
        self.assertFalse(version.branch)
        self.assertEqual(str(version), "SVN-trunk-r252849")
        self.assertEqual(version.name, "trunk")
        self.assertEqual(version.revision, 252849)

    def test_svn_version_trunk_2(self):
        """Test parsing a modified trunk version with revision"""
        version = AsteriskVersion("Asterisk SVN-trunk-r252849M")
        self.assertTrue(version.svn)
        self.assertFalse(version.branch)
        self.assertEqual(str(version), "Asterisk SVN-trunk-r252849M")
        self.assertEqual(version.name, "trunk")
        self.assertEqual(version.revision, 252849)

    def test_svn_version_teambranch_1(self):
        """Test parsing a rather long team branch"""
        version = AsteriskVersion("SVN-russell-cdr-q-r249059M-/trunk")
        self.assertTrue(version.svn)
        self.assertFalse(version.branch)
        self.assertEqual(str(version), "SVN-russell-cdr-q-r249059M-/trunk")
        self.assertEqual(version.name, "russell-cdr-q")
        self.assertEqual(version.revision, 249059)
        self.assertEqual(version.parent, "/trunk")

    def test_svn_version_teambranch_2(self):
        """Test parsing a slightly shorter team branch"""
        version = AsteriskVersion("Asterisk SVN-russell-rest-r12345")
        self.assertTrue(version.svn)
        self.assertFalse(version.branch)
        self.assertEqual(str(version), "Asterisk SVN-russell-rest-r12345")
        self.assertEqual(version.name, "russell-rest")
        self.assertEqual(version.revision, 12345)

    def test_svn_branch_10_1(self):
        """Test parsing an Asterisk 10 version branch"""
        version = AsteriskVersion("SVN-branch-10-r11111")
        self.assertTrue(version.svn)
        self.assertTrue(version.branch)
        self.assertEqual(str(version), "SVN-branch-10-r11111")
        self.assertEqual(version.major, 10)
        self.assertEqual(version.minor, 0)
        self.assertEqual(version.patch, 0)
        self.assertEqual(version.revision, 11111)

    def test_svn_branch_18_features_1(self):
        """Test parsing a 1.8 branch with features"""
        ver = "SVN-branch-1.8-digiumphones-r357808-/branches/1.8"
        version = AsteriskVersion(ver)
        self.assertTrue(version.svn)
        self.assertTrue(version.branch)
        self.assertEqual(version.major, 8)
        self.assertEqual(version.minor, 0)
        self.assertEqual(version.patch, 0)
        self.assertEqual(version.revision, 357808)
        self.assertEqual(version.parent, '/branches/1.8')
        self.assertTrue(version.feature, 'digiumphones')

    def test_svn_branch_10_features_1(self):
        """Test parsing a 10 branch with features"""
        ver = "SVN-branch-10-digiumphones-r365402-/branches/10"
        version = AsteriskVersion(ver)
        self.assertTrue(version.svn)
        self.assertTrue(version.branch)
        self.assertEqual(version.major, 10)
        self.assertEqual(version.minor, 0)
        self.assertEqual(version.patch, 0)
        self.assertEqual(version.revision, 365402)
        self.assertEqual(version.parent, '/branches/10')
        self.assertEqual(version.feature, 'digiumphones')

    def test_svn_branch_10_features_2(self):
        """Test parsing another 10 feature branch"""
        ver = "Asterisk SVN-branch-10-digiumphones-r365402"
        version = AsteriskVersion(ver)
        self.assertTrue(version.svn)
        self.assertTrue(version.branch)
        self.assertEqual(version.major, 10)
        self.assertEqual(version.minor, 0)
        self.assertEqual(version.patch, 0)
        self.assertEqual(version.revision, 365402)
        self.assertEqual(version.feature, 'digiumphones')

    def test_version_10_with_features_and_modifier(self):
        """Test parsing a 10 feature branch with a modifier"""
        version = AsteriskVersion("Asterisk 10.6.1-digiumphones-beta3")
        self.assertFalse(version.svn)
        self.assertFalse(version.branch)
        self.assertEqual(version.major, 10)
        self.assertEqual(version.minor, 6)
        self.assertEqual(version.patch, 1)
        self.assertEqual(version.feature, 'digiumphones')
        self.assertEqual(version.modifier, 'beta')
        self.assertEqual(version.iteration, 3)

    def test_svn_1811_certified_1(self):
        """Test a CA 1.8 version tag"""
        version = AsteriskVersion("Asterisk 1.8.11-cert1")
        self.assertFalse(version.svn)
        self.assertFalse(version.branch)
        self.assertEqual(version.major, 8)
        self.assertEqual(version.minor, 11)
        self.assertEqual(version.patch, 1)
        self.assertEqual(version.feature, 'cert')

    def test_svn_1811_certified_2(self):
        """Test another CA 1.8 version tag"""
        version = AsteriskVersion("1.8.11-cert2")
        self.assertFalse(version.svn)
        self.assertFalse(version.branch)
        self.assertEqual(version.major, 8)
        self.assertEqual(version.minor, 11)
        self.assertEqual(version.patch, 2)
        self.assertEqual(version.feature, 'cert')

    def test_svn_1811_certified_3(self):
        """Test a CA 1.8 version tag with modifier"""
        version = AsteriskVersion("Asterisk 1.8.11-cert3-rc1")
        self.assertFalse(version.svn)
        self.assertFalse(version.branch)
        self.assertEqual(version.major, 8)
        self.assertEqual(version.minor, 11)
        self.assertEqual(version.patch, 3)
        self.assertEqual(version.feature, 'cert')
        self.assertEqual(version.modifier, 'rc')
        self.assertEqual(version.iteration, 1)

    def test_svn_1811_certified_branch(self):
        """Test a CA 1.8 version branch"""
        version = AsteriskVersion("Asterisk SVN-branch-1.8.11-cert-r368608")
        self.assertTrue(version.svn)
        self.assertTrue(version.branch)
        self.assertEqual(version.major, 8)
        self.assertEqual(version.minor, 11)
        self.assertEqual(version.patch, 0)
        self.assertEqual(version.feature, 'cert')
        self.assertEqual(version.revision, 368608)

    def test_git_11_branch(self):
        """Test a Git checkout from master"""
        version = AsteriskVersion("Asterisk GIT-11-a987f3")
        self.assertFalse(version.svn)
        self.assertTrue(version.git)
        self.assertTrue(version.branch)
        self.assertEqual(version.major, 11)
        self.assertEqual(version.minor, 0)
        self.assertEqual(version.patch, 0)
        self.assertEqual(version.revision, "a987f3")

    def test_git_116_certified_branch(self):
        """Test a Git checkout from master"""
        version = AsteriskVersion("Asterisk GIT-11.6-cert-a987f3")
        self.assertFalse(version.svn)
        self.assertTrue(version.git)
        self.assertTrue(version.branch)
        self.assertTrue(version.branch)
        self.assertEqual(version.major, 11)
        self.assertEqual(version.minor, 6)
        self.assertEqual(version.patch, 0)
        self.assertEqual(version.feature, 'cert')
        self.assertEqual(version.name, None)
        self.assertEqual(version.revision, "a987f3")

    def test_git_master(self):
        """Test a Git checkout from master"""
        version = AsteriskVersion("Asterisk GIT-master-a987f3")
        self.assertFalse(version.svn)
        self.assertTrue(version.git)
        self.assertTrue(version.branch)
        self.assertEqual(version.name, "master")
        self.assertEqual(version.revision, "a987f3")

    def test_cmp1(self):
        """Compare two trunk versions, an 11 tag, and a 1.8 branch"""
        version1 = AsteriskVersion("SVN-trunk-r252849")
        version2 = AsteriskVersion("SVN-branch-1.8-r245581M")
        version3 = AsteriskVersion("Asterisk 11.0.1")
        version4 = AsteriskVersion("SVN-trunk-r300000")
        self.assertTrue(version1 > version2)
        self.assertTrue(version1 > version3)
        self.assertFalse(version1 > version4)

    def test_cmp2(self):
        """Compare trunk against a team branch"""
        version1 = AsteriskVersion("SVN-trunk-r252849")
        version2 = AsteriskVersion("SVN-russell-cdr-q-r249059M-/trunk")
        self.assertTrue(version1 > version2)

    def test_cmp3(self):
        """Compare 10 branch against 1.8 branch"""
        version1 = AsteriskVersion("SVN-branch-10-r245581M")
        version2 = AsteriskVersion("SVN-branch-1.8-r245581M")
        self.assertTrue(version1 > version2)

    def test_cmp4(self):
        """Compare two version tags"""
        version1 = AsteriskVersion("10.0")
        version2 = AsteriskVersion("1.8")
        self.assertTrue(version1 > version2)

    def test_cmp5(self):
        """Compare the simplest version tags"""
        version1 = AsteriskVersion("10")
        version2 = AsteriskVersion("1.8")
        self.assertTrue(version1 > version2)

    def test_cmp6(self):
        """Compare trunk against 10 branch"""
        version1 = AsteriskVersion("SVN-trunk-r245581")
        version2 = AsteriskVersion("SVN-branch-10-r251232")
        self.assertTrue(version1 > version2)

    def test_cmp16(self):
        """Compare two versions, one with a modifier"""
        version1 = AsteriskVersion("1.8.6.0-rc1")
        version2 = AsteriskVersion("1.8.6.0")
        self.assertTrue(version1 < version2)

    def test_cmp17(self):
        """Compare two modifiers"""
        version1 = AsteriskVersion("1.8.8.0-beta1")
        version2 = AsteriskVersion("1.8.8.0-rc1")
        self.assertTrue(version1 < version2)

    def test_cmp18(self):
        """Compare two versions with the same modifier"""
        version1 = AsteriskVersion("1.8.6.0-rc2")
        version2 = AsteriskVersion("1.8.6.0-rc1")
        self.assertTrue(version1 > version2)

    def test_cmp19(self):
        """Compare a high modifier against the next higher version"""
        version1 = AsteriskVersion("1.8.6.1")
        version2 = AsteriskVersion("1.8.6.0-rc11")
        self.assertTrue(version1 > version2)

    def test_cmp20(self):
        """Compare two versions with a regression/security difference"""
        version1 = AsteriskVersion("1.8.5.0")
        version2 = AsteriskVersion("1.8.5.1")
        self.assertTrue(version1 < version2)

    def test_cmp21(self):
        """Compare a tag against the same major version branch"""
        version1 = AsteriskVersion("1.8.10")
        version2 = AsteriskVersion("SVN-branch-1.8-r360138")
        self.assertTrue(version1 < version2)

    def test_cmp22(self):
        """Compare a tag against a modified same major version branch"""
        version1 = AsteriskVersion("1.8.10")
        version2 = AsteriskVersion("SVN-branch-1.8-r360138M")
        self.assertTrue(version1 < version2)

    def test_cmp23(self):
        """Compare the same CA version with a patch difference"""
        version1 = AsteriskVersion("1.8.11-cert1")
        version2 = AsteriskVersion("1.8.11-cert2")
        self.assertTrue(version1 < version2)

    def test_cmp24(self):
        """Compare two CA versions"""
        version1 = AsteriskVersion("1.8.11-cert1")
        version2 = AsteriskVersion("1.8.15-cert1")
        self.assertTrue(version1 < version2)

    def test_cmp25(self):
        """Compare a CA version against a standard release from the branch"""
        version1 = AsteriskVersion("1.8.11-cert1")
        version2 = AsteriskVersion("1.8.13.0")
        self.assertTrue(version1 < version2)

    def test_cmp26(self):
        """Compare a CA branch against a tagged version"""
        version1 = AsteriskVersion("SVN-branch-1.8.11-cert-r363674")
        version2 = AsteriskVersion("1.8.12.0")
        self.assertTrue(version1 < version2)

    def test_cmp27(self):
        """Compare two CA branches"""
        version1 = AsteriskVersion("SVN-branch-1.8.11-r363674")
        version2 = AsteriskVersion("SVN-branch-1.8.15-r363674")
        self.assertTrue(version1 < version2)

    def test_cmp28(self):
        """Compare a CA branch against the standard branch"""
        version1 = AsteriskVersion("SVN-branch-1.8.11-r363674")
        version2 = AsteriskVersion("SVN-branch-1.8-r369138M")
        self.assertTrue(version1 < version2)

    def test_cmp29(self):
        """Compare a CA version against a CA branch"""
        version1 = AsteriskVersion("1.8.11-cert1")
        version2 = AsteriskVersion("Asterisk SVN-branch-1.8.11-cert-r368608")
        self.assertTrue(version1 < version2)

    def test_cmp_git_18_11(self):
        """Compare a Git 1.8 branch to an 11 branch"""
        version1 = AsteriskVersion("Asterisk GIT-1.8-18has09")
        version2 = AsteriskVersion("Asterisk GIT-11-81yhas90")
        self.assertTrue(version1 < version2)

    def test_cmp_git_11(self):
        """Compare two Git 11 branch versions"""
        version1 = AsteriskVersion("Asterisk GIT-11-a9suh193")
        version2 = AsteriskVersion("Asterisk GIT-11-aj981bnd")
        self.assertTrue(version1 != version2)
        self.assertFalse(version1 < version2)
        self.assertFalse(version1 > version2)
        self.assertFalse(version1 == version2)

    def test_cmp_git_1811_1811branch(self):
        """Compare a CA version against a Git CA branch"""
        version1 = AsteriskVersion("1.8.11-cert2")
        version2 = AsteriskVersion("Asterisk GIT-1.8.11-cert-89haskljh")
        self.assertTrue(version1 < version2)


def main():
    """Run the unit tests"""
    unittest.main()


if __name__ == "__main__":
    main()
