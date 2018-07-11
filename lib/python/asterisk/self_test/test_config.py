#!/usr/bin/env python
"""Asterisk Configuration File Handling Unit Tests.

Copyright (C) 2010, Digium, Inc.
Russell Bryant <russell@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
"""

from harness_shared import main
import unittest
from asterisk.config import ConfigFile


class ConfigFileTests(unittest.TestCase):
    """Unit tests for ConfigFile"""

    def test_conf(self):
        """Test parsing a blob of config data"""
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

        conf = ConfigFile(filename=None, config_str=test)

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


if __name__ == "__main__":
    main()
