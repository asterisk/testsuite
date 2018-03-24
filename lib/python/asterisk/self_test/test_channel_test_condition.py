#!/usr/bin/env python
"""Tests for test condition for channels

Copyright (C) 2011-2012, Digium, Inc.
Matt Jordan <mjordan@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
"""

from harness_shared import AstMockOutput, main
import unittest
from asterisk.channel_test_condition import ChannelTestCondition


class AstMockObjectInactive(AstMockOutput):
    """mock cli output showing no active channels"""

    def cli_exec(self, command):
        """presume command is core show channels and generate output"""
        output = ""
        output += "Channel              Location             State   Application(Data)\n"
        output += "0 active channels\n"
        output += "0 active calls\n"
        output += "2 calls processed\n"
        output += "Asterisk ending (0).\n"
        return self.MockDefer(output)


class AstMockObjectSingle(AstMockOutput):
    """mock cli output showing single active channel"""

    def cli_exec(self, command):
        """presume command is core show channels and generate output"""
        output = ""
        output += "Channel              Location             State   Application(Data)\n"
        output += "Local/123@default-00 (None)               Down    ()\n"
        output += "1 active channels\n"
        output += "0 active calls\n"
        output += "2 calls processed\n"
        output += "Asterisk ending (0).\n"
        return self.MockDefer(output)


class AstMockObjectMultiple(AstMockOutput):
    """mock cli output showing multiple active channels"""

    def cli_exec(self, command):
        """presume command is core show channels and generate output"""
        output = ""
        output += "Channel              Location             State   Application(Data)\n"
        output += "PJSIP/123@default-00 (None)               Down    ()\n"
        output += "Local/123@default-00 (None)               Down    ()\n"
        output += "SIP/alice@default-00 (None)               Down    ()\n"
        output += "3 active channels\n"
        output += "0 active calls\n"
        output += "2 calls processed\n"
        output += "Asterisk ending (0).\n"
        return self.MockDefer(output)


class AstMockObjectLeaked(AstMockOutput):
    """mock cli output showing leaked channel"""

    def cli_exec(self, command):
        """presume command is core show channels and generate output"""
        output = ""
        output += "Channel              Location             State   Application(Data)\n"
        output += "Local/123@default-00 (None)               Down    ()\n"
        output += "0 active channels\n"
        output += "0 active calls\n"
        output += "2 calls processed\n"
        output += "Asterisk ending (0).\n"
        return self.MockDefer(output)


class TestConfig(object):
    """Fake TestConfig object for unittest"""

    def __init__(self):
        self.class_type_name = "bogus"
        self.config = {}
        self.enabled = True
        self.pass_expected = True


class ChannelTestConditionUnitTest(unittest.TestCase):
    """Unit Tests for ChannelTestCondition"""

    def test_evaluate_inactive(self):
        """test inactive channel condition"""
        obj = ChannelTestCondition(TestConfig())
        obj.register_asterisk_instance(AstMockObjectInactive())
        obj.evaluate()
        self.assertEqual(obj.get_status(), 'Passed')

    def test_evaluate_multiple_fail(self):
        """test multiple channel condition"""
        obj = ChannelTestCondition(TestConfig())
        obj.register_asterisk_instance(AstMockObjectMultiple())
        obj.evaluate()
        self.assertEqual(obj.get_status(), 'Failed')

    def test_evaluate_multiple_fail2(self):
        """test multiple channel condition"""
        obj = ChannelTestCondition(TestConfig())
        obj.allowed_channels = 2
        obj.register_asterisk_instance(AstMockObjectMultiple())
        obj.evaluate()
        self.assertEqual(obj.get_status(), 'Failed')

    def test_evaluate_multiple_pass(self):
        """test multiple channel condition"""
        obj = ChannelTestCondition(TestConfig())
        obj.allowed_channels = 3
        obj.register_asterisk_instance(AstMockObjectMultiple())
        obj.evaluate()
        self.assertEqual(obj.get_status(), 'Passed')

    def test_evaluate_single_fail(self):
        """test single channel condition"""
        obj = ChannelTestCondition(TestConfig())
        obj.register_asterisk_instance(AstMockObjectSingle())
        obj.evaluate()
        self.assertEqual(obj.get_status(), 'Failed')

    def test_evaluate_single_pass(self):
        """test single channel condition"""
        obj = ChannelTestCondition(TestConfig())
        obj.allowed_channels = 1
        obj.register_asterisk_instance(AstMockObjectSingle())
        obj.evaluate()
        self.assertEqual(obj.get_status(), 'Passed')

    def test_evaluate_leaked(self):
        """test leaked channel condition"""
        obj = ChannelTestCondition(TestConfig())
        obj.register_asterisk_instance(AstMockObjectLeaked())
        obj.evaluate()
        self.assertEqual(obj.get_status(), 'Failed')


if __name__ == "__main__":
    main()
