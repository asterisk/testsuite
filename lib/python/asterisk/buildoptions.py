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


class AsteriskBuildOptions(object):
    """Tracks the build options for an instance of Asterisk"""

    def __init__(self, path=None):
        """Construct an instance of AsteriskBuildOptions

        Keyword Arguments:
        path The path to locate the buildopts.h file under
        """
        self._flags = {}

        buildopts_hdr_paths = [
            "./astroot/usr/include/asterisk/buildopts.h",
            "../include/asterisk/buildopts.h",
            "/usr/include/asterisk/buildopts.h",
            "/usr/local/include/asterisk/buildopts.h"
        ]
        if path:
            buildopts_hdr_paths.insert(0, path)
        for hdr_path in buildopts_hdr_paths:
            if (self.__parse_buildopts_file(hdr_path)):
                return
        raise Exception("Failed to open any build options files")

    def __parse_buildopts_file(self, path):
        """Extract and parse the build options"""

        ret_val = False
        file_lines = []
        try:
            with open(path, "r") as build_opt_file:
                file_lines = build_opt_file.readlines()
        except IOError:
            return ret_val
        except:
            print("Unexpected error: %s" % sys.exc_info()[0])
            return ret_val
        for line in file_lines:
            if "#define" in line:
                define_tuple = line.partition(' ')[2].partition(' ')
                if (define_tuple[0] == "" or define_tuple[2] == ""):
                    msg = ("Unable to parse build option line [%s] into "
                           "compiler flag token and value" % line)
                    print(msg)
                else:
                    flag = define_tuple[0].strip()
                    allowed = define_tuple[2].strip()
                    self._flags[flag] = allowed
                    ret_val = True

        return ret_val

    def check_option(self, build_option, expected_value="1"):
        """
        Checks if a build option has been set to an expected value

        Keyword Arguments:
        build_option   The Asterisk build option set in buildopts.h to check for
        expected_value The value the option should have. Default is 1.

        Note: if the buildOption's expectedValue is "0" (for not defined), then
        this method will return True if either the buildOption does not exist OR
        if it exists and matches.

        Returns:
        True if the build option exists and the expected value matches;
        false otherwise
        """
        if build_option in self._flags.keys():
            return expected_value == self._flags[build_option]
        elif expected_value == "0":
            return True
        return False
