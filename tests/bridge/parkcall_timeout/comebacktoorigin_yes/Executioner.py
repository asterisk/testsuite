#!/usr/bin/env python
'''
Copyright (C) 2013, Digium, Inc.
Jonathan Rose <jrose@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
'''

import sys
import logging

sys.path.append("lib/python")

LOGGER = logging.getLogger(__name__)


class Executioner(object):
    def __init__(self, module_config, test_object):
        self.ami = None
        self.alice_ami = None
        self.parked_channel = None
        test_object.register_ami_observer(self.ami_connect)
        self.test_object = test_object

        self.calls = []
        self.calls.append({'parker': 'PJSIP/alice', 'lot': 'parkinglot_test1',
                          'slot': '401', 'status': 'ANSWER', 'post': False})
        self.calls.append({'parker': 'PJSIP/alice', 'lot': 'parkinglot_test1',
                          'slot': '402', 'status': 'NOANSWER', 'post': True})
        self.calls.append({'parker': 'PJSIP/alice', 'lot': 'parkinglot_test1',
                          'slot': '403', 'status': 'BUSY', 'post': True})
        self.current_call = None
        self.current_call_post = False

        # Automatically fail if we don't remove this token.
        self.fail_token = \
            self.test_object.create_fail_token("This test should fail all the "
                                               "time right now.")

        self.userevents_received = 0
        self.failures_logged = 0
        self.parks_received = 0

    def ami_connect(self, ami):
        # We need to grab a reference to Alice's AMI if it's that one.
        if ami.id == 1:
            self.alice_ami = ami

        # UUT's AMI is the one we are watching.
        if ami.id != 0:
            return

        self.ami = ami
        self.ami.registerEvent('UserEvent', self.check_user_event)
        self.ami.registerEvent('ParkedCall', self.respond_to_park)

    def respond_to_park(self, ami, event):
        self.parks_received += 1
        new_db_value = self.parks_received
        message = {'action': 'DBPut', 'Family': 'test', 'Key': 'position',
                   'Val': new_db_value}
        self.alice_ami.sendMessage(message)
        self.current_call = self.calls.pop(0)

        # Reset the call_post flag with each new test
        self.current_call_post = False

    def user_event_match(self, event):
        num_failures = 0

        if (event.get('parker') != self.current_call['parker']):
            num_failures += 1
        if (event.get('status') != self.current_call['status']):
            num_failures += 1

        if (event.get('slot') != self.current_call['slot']):
            num_failures += 1
        if (event.get('lot') != self.current_call['lot']):
            num_failures += 1

        if (num_failures):
            LOGGER.info("Failing event: %s" % event)
            LOGGER.info("Expected values: %s" % self.current_call)

        return num_failures

    def check_parkhangup(self, ami, event):
        match_failures = self.user_event_match(event)
        if (match_failures):
            LOGGER.error("Test Phase %d: %d Mismatches were observed in a "
                         "park_postcall event. Test failed." %
                         (self.parks_received, match_failures))
            self.failures_logged += 1

        # Check if a call received a post test user event against whether or
        # not it was supposed to.
        if (self.current_call['post'] is True and not self.current_call_post):
            LOGGER.error("Test Phase %d: Test failed because this phase "
                         "should have received a post call user event and "
                         "didn't." % self.parks_received)
            self.failures_logged += 1

        if (self.current_call['post'] is False and self.current_call_post):
            LOGGER.error("Test Phase %d: Test failed because this phase "
                         "should not have received a post call user event "
                         "and did." % self.parks_received)
            self.failures_logged += 1

        # Once all the tests are complete, check final pass conditions
        if len(self.calls) == 0:
            self.test_object.remove_fail_token(self.fail_token)
            if self.failures_logged == 0:
                LOGGER.info("All phases complete and the dialplan check "
                            "showed the proper entry. Yay. Test Passed.")
                self.test_object.set_passed(True)
            else:
                LOGGER.error("Test failed with %d errors.\n" %
                             self.failures_logged)
                self.test_object.set_passed(False)

    def check_parkpostcall(self, ami, event):
        match_failures = self.user_event_match(event)
        if (match_failures):
            LOGGER.error("Test Phase %d: %d mismatches were observed in a "
                         "park_postcall event. Test failed." %
                         (self.parks_received, match_failures))
            self.failures_logged += 1

        self.current_call_post = True

    def check_user_event(self, ami, event):
        if event['userevent'] == 'park_hangup':
            self.check_parkhangup(ami, event)

        elif event['userevent'] == 'park_postcall':
            self.check_parkpostcall(ami, event)
