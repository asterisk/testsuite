#!/usr/bin/env python
'''
Copyright (C) 2012, Digium, Inc.
Kinsey Moore <kmoore@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
'''

import sys
import logging

sys.path.append("lib/python")
from TestCase import TestCase

logger = logging.getLogger(__name__)

class SimpleTestCase(TestCase):
    '''The base class for extremely simple tests requiring only a spawned call
    into the dialplan where success can be reported via a user-defined AMI
    event.'''
    event_count = 0
    expected_events = 1
    hangup_chan = None

    def __init__(self):
        TestCase.__init__(self)
        self.create_asterisk()

    def ami_connect(self, ami):
        logger.info("Initiating call to local/100@test on Echo() for simple test")

        ami.registerEvent('UserEvent', self.__event_cb)
        ami.registerEvent('Newchannel', self.__channel_cb)
        ami.originate("local/100@test", application="Echo").addErrback(self.handleOriginateFailure)

    def __channel_cb(self, ami, event):
        if not self.hangup_chan:
            self.hangup_chan = event['channel']

    def __event_cb(self, ami, event):
        if self.verify_event(event):
            self.event_count += 1
            if self.event_count == self.expected_events:
                self.passed = True
                logger.info("Test ending, hanging up channel")
                self.ami[0].hangup(self.hangup_chan).addCallbacks(
                    self.hangup)

    def hangup(self, result):
        '''Now that the channels are hung up, the test can be ended'''
        logger.info("Hangup complete, stopping reactor")
        self.stop_reactor()

    def verify_event(self, event):
        """
        Hook method used to verify values in the event.
        """
        return True

    def run(self):
        TestCase.run(self)
        self.create_ami_factory()
