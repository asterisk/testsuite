#!/usr/bin/env python
"""Test condition for channels

Copyright (C) 2011-2012, Digium, Inc.
Matt Jordan <mjordan@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
"""

from twisted.internet import defer
from test_conditions import TestCondition

class ChannelTestCondition(TestCondition):
    """Test condition that checks for the existance of channels.  If channels
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

            channel_tokens = result.output.strip().split('\n')
            active_channels = 0
            for token in channel_tokens:
                if 'active channels' in token:
                    active_channel_tokens = token.partition(' ')
                    active_channels = int(active_channel_tokens[0].strip())
            if active_channels > self.allowed_channels:
                msg = ("Detected number of active channels %d is greater than "
                       "the allowed %d on Asterisk %s" % (active_channels,
                                                          self.allowed_channels,
                                                          result.host))
                super(ChannelTestCondition, self).fail_check(msg)
            return result

        def _raise_finished(finish_deferred):
            """Raise the deferred callback"""
            finish_deferred.callback(self)
            return finish_deferred

        finish_deferred = defer.Deferred()
        # Set to pass and let a failure override
        super(ChannelTestCondition, self).pass_check()

        exec_list = [ast.cli_exec('core show channels').addCallback(__channel_callback) for ast in self.ast]
        defer.DeferredList(exec_list).addCallback(_raise_finished,
                                                  finish_deferred)
        return finish_deferred
