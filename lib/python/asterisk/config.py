#!/usr/bin/env python
"""
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


def is_blank_line(line):
    return re.match("\s*(?:;.*)?$", line) is not None


class Category:
    def __init__(self, name):
        self.options = []
        self.name = name
        self.varval_re = re.compile("""
            \s*                        # Leading whitespace
            (?P<name>[\w|,\.-]+)       # Option name
            \s*=>?\s*                  # Separator, = or =>
            (?P<value>[\w\s=@|,\.-]+)  # Option value
            (?:;.*)?$                  # Optional comment before end of line
            """, re.VERBOSE)

    def parse_line(self, line):
        match = self.varval_re.match(line)
        if match is None:
            if not is_blank_line(line):
                print "Invalid line: '%s'" % line.strip()
            return
        self.options.append((match.group("name"), match.group("value").strip()))


class ConfigFile:
    def __init__(self, fn, config_str=None):
        self.categories = []
        self.category_re = re.compile("""
            \s*                       # Leading Whitespace
            \[(?P<name>[\w,\.-]+)\]   # Category name in square brackets
            \s*(?:;.*)?$              # trailing whitespace or a comment
            """, re.VERBOSE)

        if config_str is None:
            try:
                f = open(fn, "r")
                config_str = f.read()
                f.close()
            except IOError:
                print "Failed to open config file '%s'" % fn
                return
            except:
                print "Unexpected error: %s" % sys.exc_info()[0]
                return

        config_str = self.strip_mline_comments(config_str)

        for line in config_str.split("\n"):
            self.parse_line(line)

    def strip_mline_comments(self, text):
        return re.compile(";--.*?--;", re.DOTALL).sub("", text)

    def parse_line(self, line):
        match = self.category_re.match(line)
        if match is not None:
            self.categories.append(Category(match.group("name")))
        elif len(self.categories) == 0:
            if not is_blank_line(line):
                print "Invalid line: '%s'" % line.strip()
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
            "1234 => 4242,Example Mailbox,root@localhost,,var=val\n"

        conf = ConfigFile(fn=None, config_str=test)

        self.assertEqual(len(conf.categories), 2)

        self.assertEqual(conf.categories[0].name, "foo")
        self.assertEqual(len(conf.categories[0].options), 3)
        self.assertEqual(conf.categories[0].options[0][0], "a")
        self.assertEqual(conf.categories[0].options[0][1], "b")
        self.assertEqual(conf.categories[0].options[1][0], "b")
        self.assertEqual(conf.categories[0].options[1][1], "a")
        self.assertEqual(conf.categories[0].options[2][0], "c")
        self.assertEqual(conf.categories[0].options[2][1], "d")

        self.assertEqual(conf.categories[1].name, "bar")
        self.assertEqual(len(conf.categories[1].options), 3)
        self.assertEqual(conf.categories[1].options[0][0], "a-b")
        self.assertEqual(conf.categories[1].options[0][1], "c-d")
        self.assertEqual(conf.categories[1].options[1][0], "xyz")
        self.assertEqual(conf.categories[1].options[1][1], "x|y|z")
        self.assertEqual(conf.categories[1].options[2][0], "1234")
        self.assertEqual(conf.categories[1].options[2][1],
                "4242,Example Mailbox,root@localhost,,var=val")


def main(argv=None):
    if argv is None:
        argv = sys.argv

    if len(argv) == 2:
        conf = ConfigFile(argv[1])
        for c in conf.categories:
            print "[%s]" % c.name
            for (var, val) in c.options:
                print "%s = %s" % (var, val)
    else:
        return unittest.main()

    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
