#!/usr/bin/env python
"""OpenSSL Version String Handling

Copyright (C) 2017, Digium, Inc.
George Joseph <gjoseph@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
"""

import sys
import unittest
import re
sys.path.append("lib/python")

import test_suite_utils

class OpenSSLVersion:
    """An OpenSSL Version.

    """
    def __init__(self, version=None, feature=None):
        """Construct a OpenSSL Version parser.

        Keyword Arguments:
        version The OpenSSL version string to parse.
                If not supplied, the installed version is used.
        """

        self.version = -1

        if version is None:
            try:
                from OpenSSL import SSL
                from OpenSSL.SSL import OPENSSL_VERSION_NUMBER as ivers
            except ImportError:
                return

            self.version = ivers
        else:
            self.version = self.__parse_version(version)

    def __int__(self):
        """Return the version as an integer value"""
        return self.version

    def __cmp__(self, other):
        """Compare two SIPpVersion instances against each other"""
        return cmp(self.version, other.version)

    def __ne__(self, other):
        return self.version != other.version

    def __eq__(self, other):
        return self.version == other.version

    def __parse_version(self, version_str):
        """Parse the version string"""
        vv = 0
        if version_str is not None:
            parts = re.split("(\d+)[.](\d+)[.](\d+)([a-z]+)?(?:-(.+))?", version_str)
            if parts[1]:
                vv += int(parts[1]) << 28
            if parts[2]:
                vv += int(parts[2]) << 20
            if parts[3]:
                vv += int(parts[3]) << 12
            if parts[4]:
                vv += (ord(parts[4]) - ord('a')) << 4
        return vv
