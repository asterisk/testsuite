#!/usr/bin/env python
'''
Copyright (C) 2012, Digium, Inc.
Kinsey Moore <kmoore@digium.com>
Mark Michelson <mmichelson@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
'''

import sys
import logging
import time

sys.path.append("lib/python")
from version import AsteriskVersion

LOGGER = logging.getLogger(__name__)
TOLERANCE = 1.0

class Tester(object):
    def __init__(self, module_config, test_object):
        self.ami = None
        test_object.register_ami_observer(self.ami_connect)
        test_object.register_call_end_observer(self.check_duration)
        self.test_object = test_object
        self.bridge_time = 0
        self.end_time = 0
        self.calls = []
        # First call is a timed call with no warning
        self.calls.append({'timeout': 10.0, 'numwarnings': 0, 'hangup_style': 'HANGUP_TIME'})
        # Second call is a timed call with a single warning played to the caller
        self.calls.append({'timeout': 10.0, 'numwarnings': 1, 'hangup_style': 'BRIDGE_TIMELIMIT'})
        # Third call is a timed call with a single warning played to the callee
        self.calls.append({'timeout': 10.0, 'numwarnings': 1, 'hangup_style': 'BRIDGE_TIMELIMIT'})
        # Fourth call is a timed call with a single warning played to both
        # parties
        self.calls.append({'timeout': 10.0, 'numwarnings': 2, 'hangup_style': 'BRIDGE_TIMELIMIT'})
        # Fifth call is a timed call with no warning using the S() option (uses the same mechanism as L with no warning)
        self.calls.append({'timeout': 10.0, 'numwarnings': 0, 'hangup_style': 'HANGUP_TIME'})
        self.current_call = self.calls.pop(0)
        self.num_warnings = 0
        self.num_hangup_triggers = 0
        self.bridge_enters_received = 0
        return

    def ami_connect(self, ami):
        # We only care about the UUT's AMI here
        if ami.id != 0:
            return

        self.ami = ami
        self.ami.registerEvent('Hangup', self.log_hangup_time)
        self.ami.registerEvent('TestEvent', self.log_warnings)
        if AsteriskVersion() >= AsteriskVersion('12'):
            self.ami.registerEvent('BridgeEnter', self.log_bridge_enter_time)
        else:
            self.ami.registerEvent('Bridge', self.log_bridge_time)

    def log_bridge_time(self, ami, event):
        if not self.bridge_time:
            self.bridge_time = time.time()
            LOGGER.info("Bridge started at time %f" % self.bridge_time)

    def log_bridge_enter_time(self, ami, event):
        self.bridge_enters_received += 1
        if not self.bridge_time and self.bridge_enters_received == 2:
            self.bridge_time = time.time()
            LOGGER.info("Bridge started at time %f" % self.bridge_time)

    def log_hangup_time(self, ami, event):
        if not self.end_time:
            self.end_time = time.time()
            LOGGER.info("Got Timeout event at %f" % self.end_time)

    def log_warnings(self, ami, event):
        if event.get('state') == 'PLAYBACK' and event.get('message') == 'beep':
            self.num_warnings += 1
            return

        if event.get('state') == self.current_call['hangup_style']:
            self.num_hangup_triggers += 1
            return

    def check_duration(self, ami_uut, ami_alice, ami_bob):
        if not self.bridge_time or not self.end_time:
            LOGGER.error("We didn't get the notifications for duration")
            self.test_object.set_passed(False)

        duration = self.end_time - self.bridge_time

        if (abs(duration - self.current_call['timeout']) > TOLERANCE):
            LOGGER.error("Call duration was %f but we expected %f (+/- 0.5 sec)"
                    % (duration, self.current_call['timeout']))
            self.test_object.set_passed(False)

        if self.current_call['numwarnings'] != self.num_warnings:
            LOGGER.error("We expected %d warnings but got %d" %
                    (self.current_call['numwarnings'], self.num_warnings))
            self.test_object.set_passed(False)

        triggers = 1
        if self.current_call['hangup_style'] == 'BRIDGE_TIMELIMIT' \
            and AsteriskVersion() >= AsteriskVersion('12'):
            triggers = 2

        if triggers != self.num_hangup_triggers:
            LOGGER.error("We expected %d hangup trigger(s) but got %d" %
                    (triggers, self.num_hangup_triggers))
            self.test_object.set_passed(False)

        # Reset the variables for the next call
        self.bridge_enters_received = self.num_hangup_triggers = 0
        self.bridge_time = self.end_time = self.num_warnings = 0
        if len(self.calls) != 0:
            self.current_call = self.calls.pop(0)
