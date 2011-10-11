#!/usr/bin/env python
'''
Copyright (C) 2011, Digium, Inc.
Matt Jordan <mjordan@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
'''

import logging
import logging.config
import unittest

from TestConditions import TestCondition

logger = logging.getLogger(__name__)

class ChannelTestCondition(TestCondition):
    """
    Test condition that checks for the existance of channels.  If channels
    are detected and the number of active channels is greater than the
    configured amount, an error is raised.

    By default, the number of allowed active channels is 0.
    """

    def __init__(self, test_config):
        super(ChannelTestCondition, self).__init__(test_config)

        self.allowed_channels = 0
        if ('allowedchannels' in test_config.config):
            self.allowed_channels = test_config.config['allowedchannels']

    def evaluate(self, related_test_condition = None):
        for ast in self.ast:
            """ For logging / debug purposes, do a full core show channels """
            channel_lines = ast.cli_exec('core show channels')
            channel_tokens = channel_lines.strip().split('\n')
            active_channels = 0
            for token in channel_tokens:
                if 'active channels' in token:
                    active_channel_tokens = token.partition(' ')
                    active_channels = int(active_channel_tokens[0].strip())
            if active_channels > self.allowed_channels:
                super(ChannelTestCondition, self).failCheck(
                    'Detected number of active channels %d is greater than the allowed %d on Asterisk %s' % (active_channels, self.allowed_channels, ast.host))
        """ Set to pass if we haven't detected any failures """
        super(ChannelTestCondition, self).passCheck()

