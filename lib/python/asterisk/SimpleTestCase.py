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

LOGGER = logging.getLogger(__name__)

class SimpleTestCase(TestCase):
    '''The base class for extremely simple tests requiring only a spawned call
    into the dialplan where success can be reported via a user-defined AMI
    event.'''
    event_count = 0
    expected_events = 1

    def __init__(self):
        TestCase.__init__(self)
        self.create_asterisk()

    def ami_connect(self, ami):
        LOGGER.info("Initiating call to local/100@test on Echo() for simple test")

        ami.registerEvent('UserEvent', self.__event_cb)
        df = ami.originate("local/100@test", application="Echo")

        def handle_failure(reason):
            LOGGER.info("error sending originate:")
            LOGGER.info(reason.getTraceback())
            self.stop_reactor()
            return reason

        df.addErrback(handle_failure)

    def __event_cb(self, ami, event):
        if self.verify_event(event):
            self.event_count += 1
            if self.event_count == self.expected_events:
                # get list of channels so hangups can happen
                df = self.ami[0].status().addCallbacks(self.status_callback,
                    self.status_failed)

    def status_callback(self, result):
        '''Initiate hangup since no more testing will take place'''
        for status_result in result:
            if 'channel' in status_result:
                self.ami[0].hangup(status_result['channel']).addCallbacks(
                    self.hangup_success)
            break
        else:
            # no channels to hang up? close it out
            self.passed = True
            self.stop_reactor()

    def hangup_success(self, result):
        '''Now that the channels are hung up, the test can be ended'''
        self.passed = True
        self.stop_reactor()

    def status_failed(self, reason):
        '''If the channel listing failed, we still need to shut down'''
        self.passed = True
        self.stop_reactor()

    def verify_event(self, event):
        """
        Hook method used to verify values in the event.
        """
        return True

    def run(self):
        TestCase.run(self)
        self.create_ami_factory()
