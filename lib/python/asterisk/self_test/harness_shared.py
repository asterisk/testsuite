"""Unit test harness

This module provides the entry-point for tests

Copyright (C) 2018, CFWare, LLC.
Corey Farrell <git@cfware.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
"""

import logging
import os
import sys
from twisted.internet import defer
import unittest

# Add directory where the modules to test can be found
sys.path.append('lib/python')


def ReadTestFile(filename, basepath="lib/python/asterisk/self_test"):
    fd = open(os.path.join(basepath, filename), "r")
    output = fd.read()
    fd.close()
    return output


class AstMockOutput(object):
    """mock cli output base class"""

    def __init__(self, host="127.0.0.1"):
        """Constructor"""
        self.host = host

    def MockDeferFile(self, filename):
        return self.MockDefer(ReadTestFile(filename))

    def MockDefer(self, output):
        """use real defer to mock deferred output"""
        self.output = output
        deferred = defer.Deferred()
        deferred.callback(self)
        return deferred


def main():
    """Run the unit tests"""

    logging.basicConfig()
    unittest.main()


__all__ = ["main", "AstMockOutput", "ReadTestFile"]
