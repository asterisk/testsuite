"""Asterisk Configuration File Handling.

This module implements interfaces for dealing with Asterisk configuration
files.

Copyright (C) 2010, Digium, Inc.
Russell Bryant <russell@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
"""

#
# TODO
# - Implement config section template handling
#

import sys
import re
import logging

LOGGER = logging.getLogger(__name__)


def is_blank_line(line):
    """Is this a blank line?"""
    return re.match("\s*(?:;.*)?$", line) is not None


class Category(object):
    """A category in an Asterisk configuration file.

    This is a helper class used along with ConfigFile.  A category is section
    of an Asterisk configuration that will contain zero or more key/value pairs
    of options.
    """

    def __init__(self, name, template=False):
        self.options = []
        self.name = name
        self.template = template
        self.varval_re = re.compile("""
            \s*                                # Leading whitespace
            (?P<name>[\w|,\.-]+)               # Option name
            \s*=>?\s*                          # Separator, = or =>
            (?P<value>[\w\s=_()/@|,'"\.<>:-]*) # Option value (can be zero-length)
            (?:;.*)?$                          # Optional comment before end of line
            """, re.VERBOSE)

    def parse_line(self, line):
        """Parse a line in a category"""
        match = self.varval_re.match(line)
        if match is None:
            if not is_blank_line(line):
                LOGGER.warning("Invalid line: '%s'" % line.strip())
            return
        self.options.append((match.group("name"), match.group("value").strip()))


class ConfigFile(object):
    """An Asterisk Configuration File.

    Parse an Asterisk configuration file.
    """

    def __init__(self, filename, config_str=None):
        """Construct an Asterisk configuration file object

        The ConfigFile object will parse an Asterisk configuration file into a
        python data structure.
        """
        self.categories = []
        self.category_re = re.compile("""
            \s*                        # Leading Whitespace
            \[(?P<name>[\w,\.-]+)\]    # Category name in square brackets
            (?:\((?P<template>[!])\))? # Optionally marked as a template
            \s*(?:;.*)?$               # trailing whitespace or a comment
            """, re.VERBOSE)

        if config_str is None:
            try:
                with open(filename, "r") as config_file:
                    config_str = config_file.read()
            except IOError:
                LOGGER.error("Failed to open config file '%s'" % filename)
                return
            except:
                LOGGER.error("Unexpected error: %s" % sys.exc_info()[0])
                return

        config_str = self.strip_mline_comments(config_str)

        for line in config_str.split("\n"):
            self.parse_line(line)

    def strip_mline_comments(self, text):
        """Strip multi-line comments"""
        return re.compile(";--.*?--;", re.DOTALL).sub("", text)

    def parse_line(self, line):
        """Parse a line in the config file"""
        match = self.category_re.match(line)
        if match is not None:
            self.categories.append(
                Category(match.group("name"),
                         template=match.group("template") == "!")
            )
        elif len(self.categories) == 0:
            if not is_blank_line(line):
                LOGGER.warning("Invalid line: '%s'" % line.strip())
        else:
            self.categories[-1].parse_line(line)
