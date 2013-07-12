#!/usr/bin/env python
"""Asterisk Build Options Handling

This module implements an Asterisk build options parser.  It
tracks what build options Asterisk was compiled with, and returns
whether or not a particular build option was enabled.

Copyright (C) 2011-2012, Digium, Inc.
Matt Jordan <mjordan@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
"""

import sys
import re
import unittest
import logging

class AsteriskBuildOptions:
    """
    Tracks the build options for an instance of Asterisk
    """

    def __init__(self, path=None):
        """
        Construct an instance of AsteriskBuildOptions

        Keyword Arguments:
        path -- the path to locate the buildopts.h file under
        """
        self.__flags = {}

        buildopts_hdr_paths = [
            "../include/asterisk/buildopts.h",
            "/usr/include/asterisk/buildopts.h",
            "/usr/local/include/asterisk/buildopts.h"
        ]
        if path:
            buildopts_hdr_paths.insert(0, path)
        for p in buildopts_hdr_paths:
            if (self.__parse_buildopts_file(p)):
                return
        raise Exception("Failed to open any build options files")


    def __parse_buildopts_file(self, path):
        retVal = False
        try:
            f = open(path, "r")
            fileLines = f.readlines()
            f.close()
        except IOError:
            return retVal
        except:
            print "Unexpected error: %s" % sys.exc_info()[0]
            return retVal
        for line in fileLines:
            if "#define" in line:
                defineTuple = line.partition(' ')[2].partition(' ')
                if (defineTuple[0] == "" or defineTuple[2] == ""):
                    print "Unable to parse build option line [%s] into compiler flag token and value" % line
                else:
                    self.__flags[defineTuple[0].strip()] = defineTuple[2].strip()
                    retVal = True

        return retVal

    def checkOption(self, buildOption, expectedValue = "1"):
        """
        Checks if a build option has been set to an expected value

        Keyword Arguments:
        buildOption -- the Asterisk build option set in buildopts.h to check for
        expectedValue -- (optional) - the value the option should have.  Default is 1.

        Note: if the buildOption's expectedValue is "0" (for not defined), then this method
        will return True if either the buildOption does not exist OR if it exists and matches.

        returns True if the build option exists and the expected value matches; false otherwise
        """
        if buildOption in self.__flags.keys():
            return expectedValue == self.__flags[buildOption]
        elif expectedValue == "0":
            return True
        return False

class AsteriskBuildOptionsTests(unittest.TestCase):
    def test_1(self):
        b1 = AsteriskBuildOptions()
        self.assertTrue(1)


def main():
    unittest.main()


if __name__ == "__main__":
    main()
