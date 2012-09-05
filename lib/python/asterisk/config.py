#!/usr/bin/env python
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
import unittest
import logging

logger = logging.getLogger(__name__)

def is_blank_line(line):
    return re.match("\s*(?:;.*)?$", line) is not None


class Category:
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
        match = self.varval_re.match(line)
        if match is None:
            if not is_blank_line(line):
                logger.warn("Invalid line: '%s'" % line.strip())
            return
        self.options.append((match.group("name"), match.group("value").strip()))


class ConfigFile:
    """An Asterisk Configuration File.

    Parse an Asterisk configuration file.
    """

    def __init__(self, fn, config_str=None):
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
                f = open(fn, "r")
                config_str = f.read()
                f.close()
            except IOError:
                logger.error("Failed to open config file '%s'" % fn)
                return
            except:
                logger.error("Unexpected error: %s" % sys.exc_info()[0])
                return

        config_str = self.strip_mline_comments(config_str)

        for line in config_str.split("\n"):
            self.parse_line(line)

    def strip_mline_comments(self, text):
        return re.compile(";--.*?--;", re.DOTALL).sub("", text)

    def parse_line(self, line):
        match = self.category_re.match(line)
        if match is not None:
            self.categories.append(
                Category(match.group("name"), 
                    template=match.group("template") == "!")
            )
        elif len(self.categories) == 0:
            if not is_blank_line(line):
                logger.warn("Invalid line: '%s'" % line.strip())
        else:
            self.categories[-1].parse_line(line)


class ConfigFileTests(unittest.TestCase):
    def test_conf(self):
        test = \
            "; stuff\n" \
            "this line is invalid on purpose\n" \
            "[this is] also invalid]\n" \
            ";-- comment --;\n" \
            ";--   \n" \
            "[this is commented out]\n" \
            "         --;\n" \
            "[foo]\n" \
            "a = b\n" \
            "  b =   a  \n" \
            "this line is invalid on purpose\n" \
            ";moo\n" \
            "c = d;asdadf;adfads;adsfasdf\n" \
            "  [bar]   ;asdfasdf\n" \
            "a-b=c-d\n" \
            "xyz=x|y|z\n" \
            "1234 => 4242,Example Mailbox,root@localhost,,var=val\n" \
            "\n" \
            "[template](!)\n" \
            "foo=bar\n" \
            "exten => _NXX.,n,Wait(1)\n" \
            "astetcdir => /etc/asterisk\n"

        conf = ConfigFile(fn=None, config_str=test)

        self.assertEqual(len(conf.categories), 3)

        self.assertEqual(conf.categories[0].name, "foo")
        self.assertFalse(conf.categories[0].template)
        self.assertEqual(len(conf.categories[0].options), 3)
        self.assertEqual(conf.categories[0].options[0][0], "a")
        self.assertEqual(conf.categories[0].options[0][1], "b")
        self.assertEqual(conf.categories[0].options[1][0], "b")
        self.assertEqual(conf.categories[0].options[1][1], "a")
        self.assertEqual(conf.categories[0].options[2][0], "c")
        self.assertEqual(conf.categories[0].options[2][1], "d")

        self.assertEqual(conf.categories[1].name, "bar")
        self.assertFalse(conf.categories[1].template)
        self.assertEqual(len(conf.categories[1].options), 3)
        self.assertEqual(conf.categories[1].options[0][0], "a-b")
        self.assertEqual(conf.categories[1].options[0][1], "c-d")
        self.assertEqual(conf.categories[1].options[1][0], "xyz")
        self.assertEqual(conf.categories[1].options[1][1], "x|y|z")
        self.assertEqual(conf.categories[1].options[2][0], "1234")
        self.assertEqual(conf.categories[1].options[2][1],
                "4242,Example Mailbox,root@localhost,,var=val")

        self.assertEqual(conf.categories[2].name, "template")
        self.assertTrue(conf.categories[2].template)
        self.assertEqual(len(conf.categories[2].options), 3)
        self.assertEqual(conf.categories[2].options[0][0], "foo")
        self.assertEqual(conf.categories[2].options[0][1], "bar")
        self.assertEqual(conf.categories[2].options[1][0], "exten")
        self.assertEqual(conf.categories[2].options[1][1],
                "_NXX.,n,Wait(1)")
        self.assertEqual(conf.categories[2].options[2][0], "astetcdir")
        self.assertEqual(conf.categories[2].options[2][1], "/etc/asterisk")


def main(argv=None):
    if argv is None:
        argv = sys.argv

    if len(argv) == 2:
        conf = ConfigFile(argv[1])
        for c in conf.categories:
            logger.debug("[%s]" % c.name)
            for (var, val) in c.options:
                logger.debug("%s = %s" % (var, val))
    else:
        return unittest.main()

    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
