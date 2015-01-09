#!/usr/bin/env python
"""Test condition for channels

Copyright (C) 2011-2012, Digium, Inc.
Matt Jordan <mjordan@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
"""

from twisted.internet import defer
from test_conditions import TestCondition
import logging
import unittest
import re


class ChannelTestCondition(TestCondition):
    """Test condition that checks for the existence of channels.  If channels
    are detected and the number of active channels is greater than the
    configured amount, an error is raised.

    By default, the number of allowed active channels is 0.
    """

    def __init__(self, test_config):
        """Constructor

        Keyword Arguments:
        test_config The TestConfig object for the test
        """
        super(ChannelTestCondition, self).__init__(test_config)

        self.allowed_channels = 0
        if ('allowedchannels' in test_config.config):
            self.allowed_channels = test_config.config['allowedchannels']

    def evaluate(self, related_test_condition=None):
        """Evaluate this test condition

        Keyword Argument:
        related_test_condition The test condition that this condition is
                                related to

        Returns:
        A deferred that will be called when evaluation is complete
        """
        def __channel_callback(result):
            """Callback called from core show channels"""

            channel_expression = re.compile('^[A-Za-z0-9]+/')
            channel_tokens = result.output.strip().split('\n')
            active_channels = 0
            referenced_channels = 0
            for token in channel_tokens:
                if channel_expression.match(token):
                    referenced_channels += 1
                if 'active channels' in token:
                    active_channel_tokens = token.partition(' ')
                    active_channels = int(active_channel_tokens[0].strip())
            if active_channels > self.allowed_channels:
                msg = ("Detected number of active channels %d is greater than "
                       "the allowed %d on Asterisk %s" %
                       (active_channels, self.allowed_channels, result.host))
                super(ChannelTestCondition, self).fail_check(msg)
            elif referenced_channels > self.allowed_channels:
                msg = ("Channel leak detected - "
                       "number of referenced channels %d is greater than "
                       "the allowed %d on Asterisk %s" %
                       (referenced_channels, self.allowed_channels,
                        result.host))
                super(ChannelTestCondition, self).fail_check(msg)
            return result

        def _raise_finished(result, finish_deferred):
            """Raise the deferred callback"""
            finish_deferred.callback(self)
            return result

        finish_deferred = defer.Deferred()
        # Set to pass and let a failure override
        super(ChannelTestCondition, self).pass_check()

        exec_list = [ast.cli_exec('core show channels').
                     addCallback(__channel_callback) for ast in self.ast]
        defer.DeferredList(exec_list).addCallback(_raise_finished,
                                                  finish_deferred)
        return finish_deferred


class AstMockOutput(object):
    """mock cli output base class"""

    def __init__(self):
        """Constructor"""
        self.host = "127.0.0.1"

    def MockDefer(self, output):
        """use real defer to mock deferred output"""
        self.output = output
        deferred = defer.Deferred()
        deferred.callback(self)
        return deferred


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


def main():
    """Run the unit tests"""

    logging.basicConfig(level=logging.DEBUG)
    unittest.main()

if __name__ == "__main__":
    main()
