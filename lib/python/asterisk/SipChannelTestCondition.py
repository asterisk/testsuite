#!/usr/bin/env python
'''
Copyright (C) 2013, Digium, Inc.
Nitesh Bansal <nitesh.bansal@gmail.com>
Matt Jordan <mjordan@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
'''

import logging
import logging.config
import unittest

from twisted.internet import defer
from TestConditions import TestCondition

logger = logging.getLogger(__name__)

class SipChannelTestCondition(TestCondition):
    """
    Test condition that checks for the existance of SIP channels.  If channels
    are detected and the number of active channels is greater than the
    configured amount, an error is raised.

    By default, the number of allowed active channels is 0.
    """

    def __init__(self, test_config):
        super(SipChannelTestCondition, self).__init__(test_config)

        self.allowed_channels = 0
        if ('allowedchannels' in test_config.config):
            self.allowed_channels = test_config.config['allowedchannels']

    def evaluate(self, related_test_condition = None):
        def __channel_callback(result):
            channel_tokens = result.output.strip().split('\n')
            active_channels = 0
            for token in channel_tokens:
                if 'active SIP channel' in token:
                    active_channel_tokens = token.partition(' ')
                    active_channels = int(active_channel_tokens[0].strip())
            if active_channels > self.allowed_channels:
                super(SipChannelTestCondition, self).failCheck(
                    'Detected number of active SIP channels %d is greater than the allowed %d on Asterisk %s'
                     % (active_channels, self.allowed_channels, result.host))
            return result

        def __raise_finished(result):
            self.__finished_deferred.callback(self)
            return result

        self.__finished_deferred = defer.Deferred()
        # Set to pass and let a failure override
        super(SipChannelTestCondition, self).passCheck()

        defer.DeferredList([ast.cli_exec('sip show channels').addCallback(__channel_callback) for ast in self.ast]
                           ).addCallback(__raise_finished)
        return self.__finished_deferred
