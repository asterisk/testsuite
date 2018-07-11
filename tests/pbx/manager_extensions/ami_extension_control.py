#!/usr/bin/env python
'''
Copyright (C) 2014, Digium, Inc.
Jonathan Rose <jrose@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
'''

import logging
from asterisk.test_case import TestCase
from twisted.internet import defer

LOGGER = logging.getLogger(__name__)


class AMIExtensionControl(TestCase):
    """Specialized test case that performs AMI actions and checks their
    results as defined by the test-config and then originates a series
    of calls to channels defined by the test-config.
    """

    def __init__(self, path=None, test_config=None):
        """Create an AMIExtensionControl TestCase.

        Keyword Arguments:
        test_path Optional parameter that specifies the path where this test
                  resides
        test_config Loaded YAML test configuration
        """

        super(AMIExtensionControl, self).__init__(path, test_config)

        if test_config is None:
            raise Exception("No configuration provided")

        self.commands = test_config['commands']
        self.originates = test_config['originates']
        self.responses_received = 0
        self.test_ami = None  # Will be set on ami_connect
        self.create_asterisk()

    def originate_calls(self):
        """Originates channels defined by the test-config to originate@test
        """

        def _pass_test(results, test_object):
            """ Validates the results of all originate actions
            """
            passed = all(result[0] for result in results if result[0])
            test_object.set_passed(passed)

        deferds = []
        for channel in self.originates:
            deferred = self.test_ami.originate(channel=channel['channel'],
                                               exten='originate',
                                               context='test',
                                               priority='1',
                                               timeout='5',
                                               callerid='"test_id" <1337>')
            deferred.addErrback(self.handle_originate_failure)
            deferds.append(deferred)

        deferred_list = defer.DeferredList(deferds)
        deferred_list.addCallback(_pass_test, self)

    def response_received(self):
        """Tracks the number of responses received to the test-config defined
        AMI actions. Once the responses received adds up to the number of
        actions performed, the origination portion of the test will be
        started.
        """

        self.responses_received += 1

        if self.responses_received == len(self.commands):
            self.originate_calls()

    def run(self):
        """Run the test as normal for a TestCase and start an AMI instance
        """

        super(AMIExtensionControl, self).run()
        self.create_ami_factory()

    def ami_connect(self, ami):
        """On AMI connect, run through all of the AMI commands defined by
        the test-config.
        """

        def _expect_success(message):
            """Callback for when the resposnse to a message is Success.
            Verifies that the response is success and sets failure if it
            isn't. Calls response_received to bump the responses_received
            count and begin the next phase when ready.
            """

            # Check type of message because we receive a message when the
            # connection closes that isn't a dictionary.
            if type(message) is not dict:
                return 0

            if message.get('response') != 'Success':
                self.create_fail_token("Received response '%s' when "
                                       "successful response was expected."
                                       % message)
            self.response_received()
            return 0

        def _expect_error(message):
            """Same as _expect_success, only the expected response is Error.
            """

            # Check type of message because we receive a message when the
            # connection closes that isn't a dictionary.
            if type(message) is not dict:
                return 0

            if message.get('response') != 'Error':
                self.create_fail_token("Received response '%s' when error "
                                       "response was expected." % message)
            self.response_received()
            return 0

        def _handle_hangup(ami, event):
            """Responds to Hangup manager events and stops the test once a
            hangup has occured for each originate action"""
            hung_up = event.get('channel')

            for originate in self.originates:
                this_chan = originate['channel']

                if hung_up.lower().startswith(this_chan.lower()):
                    self.originates.remove(originate)
                    break

            if len(self.originates) == 0:
                self.stop_reactor()

            return 0

        self.test_ami = ami
        ami.registerEvent("Hangup", _handle_hangup)

        for action in self.commands:
            message = action['command']
            if action['expected-response'] == 'Success':
                ami.sendMessage(message, responseCallback=_expect_success)
            else:
                ami.sendMessage(message, responseCallback=_expect_error)
