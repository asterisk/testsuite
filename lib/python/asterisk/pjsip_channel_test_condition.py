'''
Copyright (C) 2018, Digium, Inc.
Torrey Searle  <tsearle@gmail.com>
Nitesh Bansal <nitesh.bansal@gmail.com>
Matt Jordan <mjordan@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
'''

from twisted.internet import defer
from test_conditions import TestCondition


class PJSipChannelTestCondition(TestCondition):
    """Test condition that checks for the existence of PJSIP channels.

    If channels are detected and the number of active channels is greater than
    the configured amount, an error is raised.

    By default, the number of allowed active channels is 0.
    """

    def __init__(self, test_config):
        """Constructor"""
        super(PJSipChannelTestCondition, self).__init__(test_config)

        self.allowed_channels = 0
        if ('allowedchannels' in test_config.config):
            self.allowed_channels = test_config.config['allowedchannels']

    def evaluate(self, related_test_condition=None):
        """Evaluate the test condition"""

        def __channel_callback(result):
            """Callback for the CLI command"""

            channel_tokens = result.output.strip().split('\n')
            active_channels = 0
            for token in channel_tokens:
                if 'Objects found: ' in token:
                    active_channels = int(token[token.find(":")+1:].strip())
            if active_channels > self.allowed_channels:
                super(PJSipChannelTestCondition, self).fail_check(
                    ("Detected number of active PJSIP channels %d is greater "
                     "than the allowed %d on Asterisk %s" %
                     (active_channels, self.allowed_channels, result.host)))
            return result

        def __raise_finished(finished_deferred):
            """Let things know when we're done"""
            finished_deferred.callback(self)
            return finished_deferred

        finished_deferred = defer.Deferred()
        # Set to pass and let a failure override
        super(PJSipChannelTestCondition, self).pass_check()

        exec_list = [ast.cli_exec('pjsip show channels').addCallback(
            __channel_callback) for ast in self.ast]
        defer.DeferredList(exec_list).addCallback(__raise_finished,
                                                  finished_deferred)
        return finished_deferred
