#!/usr/bin/env python
'''
Copyright (C) 2013, Digium, Inc.
Jonathan Rose <jrose@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
'''

import sys
import logging
import re

sys.path.append("lib/python")

LOGGER = logging.getLogger(__name__)

class Executioner(object):
    def __init__(self, module_config, test_object):
        self.ami = None
        self.parked_channel = None
        test_object.register_ami_observer(self.ami_connect)
        self.test_object = test_object

        self.calls = []
        self.calls.append({'test' : '1', 'parker' : 'SIP/alice', 'lot' : 'parkinglot_test1', 'slot' : '401'})
        self.calls.append({'test' : '2', 'parker' : 'SIP/alice', 'lot' : 'parkinglot_test2', 'slot' : '501'})
        self.calls.append({'test' : '3', 'parker' : 'SIP/alice', 'lot' : 'parkinglot_test3', 'slot' : '601'})
        self.userevents_received = 0
        self.passed_dialplan = 0
        self.failures_logged = 0
        self.fail_token = self.test_object.create_fail_token("No success indicated by Executioner.")
        return

    def ami_connect(self, ami):
        # We only care about the UUT's AMI here
        if ami.id != 0:
            return

        self.ami = ami
        self.ami.registerEvent('UserEvent', self.check_user_event)
        self.ami.registerEvent('ListDialplan', self.check_dialplan)

    def check_dialplan(self, ami, event):
        not_right = False
        if event.get('priority') != '1':
            not_right = True
        if event.get('application') != 'Dial':
            not_right = True
        if event.get('appdata') != 'SIP/alice,3,Hk':
            not_right = True
        if event.get('registrar') != 'features':
            not_right = True

        if not_right:
            # We don't handle failure here since the last check_user_event will simply see if one ever succeeded
            LOGGER.info("Received a dialplan entry that didn't match the expected one.")
            return

        LOGGER.info("Received a dialplan entry that matched our expectations.")
        self.passed_dialplan = 1

    def check_user_event(self, ami, event):

        # We are only interested in comebackexten userevents.
        if event['userevent'] != 'comebackexten':
            return

        this_expectation = self.calls.pop(0)
        self.userevents_received += 1

        # Make sure we are looking at the right test.
        if not event.get('test'):
            LOGGER.error("Test received with no test number. Test failed.")
            self.failures_logged += 1
        else:
            this_test = int(event.get('test'))

        if this_test != self.userevents_received:
            LOGGER.error("Got an out of order test.  Test failed.")
            self.failures_logged += 1

        # Make sure the test wasn't from a failure condition
        if not event.get('success'):
            LOGGER.error("Test Phase %d: User Event didn't include a success tag. Test Failed." % this_test)
            self.failures_logged += 1

        if event.get('success') != 'true':
            LOGGER.error("Test Phase %d: User Event didn't indicate success. Test Failed." % this_test)
            self.failures_logged += 1

        # Make sure each variable that was supposed to be set matches our expectations.
        mismatches = 0
        if event.get('parker') != this_expectation['parker']:
            LOGGER.error("Test Phase %d: User event condition mismatch on parker. Got '%s' but '%s' was expected." % (this_test, event.get('parker'), this_expectation['parker']))
            mismatches += 1
        if event.get('slot') != this_expectation['slot']:
            LOGGER.error("Test Phase %d: User Event condition mismatch on slot. Got '%s' but '%s' was expected." % (this_test, event.get('slot'), this_expectation['slot']))
            mismatches += 1
        if event.get('lot') != this_expectation['lot']:
            LOGGER.error("Test Phase %d: User Event condition mismatch on lot. Got '%s' but '%s' was expected." % (this_test, event.get('lot'), this_expectation['lot']))
            mismatches += 1

        if mismatches > 0:
            LOGGER.error("Test Phase %d: Mismatches were present in the channel variables set by park call timeout. Test failed." % this_test)
            self.failures_logged += 1

        # For the first test, we should also make sure the park-dial extension was added. This will require another event.
        if self.userevents_received == 1:
            message = {'action': 'ShowDialPlan', 'context': 'park-dial', 'extension': 'SIP_alice'}
            self.ami.sendMessage(message)

        # Looks like the test was successful.  Yay.
        LOGGER.info("Test Phase %d: Passed." % this_test)

        # Once all the tests are complete, we need to check final pass conditions
        if len(self.calls) == 0:
            # clear the fail token since we have reached where we decide ultimately whether it failed or not.
            self.test_object.remove_fail_token(self.fail_token)

            if not self.passed_dialplan:
                LOGGER.error("We never received a ListDialPlan event with the right extension data in it. Test failed.")
                self.failures_logged += 1
                self.test_object.set_passed(False)

            if self.failures_logged == 0:
                LOGGER.info("All phases complete and the dialplan check showed the proper entry. Yay. Test Passed.")
                self.test_object.set_passed(True)
            else:
                LOGGER.error("Test failed with %d errors.\n", self.failures_logged)
                self.test_object.set_passed(False)
