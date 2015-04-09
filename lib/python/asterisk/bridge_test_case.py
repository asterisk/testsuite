#!/usr/bin/env python
"""
Copyright (C) 2012, Digium, Inc.
Mark Michelson <mmichelson@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
"""

import sys
import logging
import os
from time import sleep

sys.path.append("lib/python")
from test_case import TestCase

LOGGER = logging.getLogger(__name__)


class BridgeTestCase(TestCase):
    """A test object for bridging tests"""

    ALICE_CONNECTED = '"Bob" <4321>'
    BOB_CONNECTED = '"Alice" <1234>'

    FEATURE_MAP = {
        'blindxfer': 1,
        'atxfer': 2,
        'disconnect': 3,
        'automon': 4,
        'automixmon': 5,
        'parkcall': 6,
        'atxferthreeway': 7,
        # other arbitrary DTMF features can be matched under DTMF code 8
        # as "unknown"
        'unknown': 8
    }

    def __init__(self, test_path='', test_config=None):
        """Class that handles tests involving two-party bridges.

        There are three Asterisk instances used for this test.
        0 : the unit under test "UUT"
        1 : the unit from which calls originate, also known as "Alice"
        2 : the unit where calls terminate, also known as "Bob"
        """
        TestCase.__init__(self, test_path)
        self.test_runs = []
        self.current_run = 0
        self.ami_uut = None
        self.ami_alice = None
        self.ami_bob = None
        self.call_end_observers = []
        self.feature_start_observers = []
        self.feature_end_observers = []
        self.instances = 3
        self.connections = 0
        self.features = []
        self.alice_channel = None
        self.bob_channel = None
        self.uut_alice_channel = None
        self.uut_bob_channel = None
        self.uut_bridge_id = None
        self.alice_hungup = False
        self.bob_hungup = False
        self.uut_alice_hungup = False
        self.uut_bob_hungup = False
        self.current_feature = 0
        self.infeatures = False
        self.issue_hangups_on_bridged = False
        self.bridged = False
        self.audio_detected = False
        self.feature_success = False

        msg = ("BridgeTestCase hasn't raised the flag to indicate completion "
               "of all expected calls.")
        self.bridge_fail_token = self.create_fail_token(msg)

        if test_config is None:
            LOGGER.error("No configuration provided. Bailing.")
            raise Exception

        # Just a quick sanity check so we can die early if
        # the tests are badly misconfigured
        for test_run in test_config['test-runs']:
            if not 'originate_channel' in test_run:
                LOGGER.error("No configured originate channel in test run")
                raise Exception

            self.test_runs.append(test_run)

        if 'asterisk-instances' in test_config:
            self.instances = test_config['asterisk-instances']
        self.create_asterisk(self.instances, "%s/configs/bridge" % os.getcwd())
        LOGGER.info("Bridge test initialized")

    def run(self):
        """Override of TestCase.run"""
        TestCase.run(self)
        self.create_ami_factory(self.instances)

    def register_feature_start_observer(self, observer):
        """Register an observer to be notified when a feature is started

        Keyword Arguments:
        observer A callback function to be called when a feature occurs. The
            callback should take two arguments. This first will be this object;
            the second will be a dict object describing the feature that just
            occurred
        """
        self.feature_start_observers.append(observer)

    def register_feature_end_observer(self, observer):
        """Register an observer to be notified when a feature is completed

        Keyword Arguments:
        observer A callback function to be called when a feature occurs. The
            callback should take two arguments. This first will be this object;
            the second will be a dict object describing the feature that just
            occurred
        """
        self.feature_end_observers.append(observer)

    def ami_connect(self, ami):
        """AMI connect handler"""

        self.connections += 1
        self.ast[ami.id].cli_exec("sip set debug on")
        self.ast[ami.id].cli_exec("iax2 set debug on")
        self.ast[ami.id].cli_exec("xmpp set debug on")
        if (ami.id == 0):
            self.ami_uut = ami
            self.ami_uut.registerEvent('Bridge', self.uut_bridge_callback)
            self.ami_uut.registerEvent('BridgeCreate',
                                       self.uut_bridge_create_callback)
            self.ami_uut.registerEvent('BridgeEnter',
                                       self.uut_bridge_enter_callback)
            self.ami_uut.registerEvent('BridgeLeave',
                                       self.uut_bridge_leave_callback)
            self.ami_uut.registerEvent('TestEvent', self.test_callback)
            self.ami_uut.registerEvent('Hangup', self.hangup_callback)
            LOGGER.info("UUT AMI connected")
        elif (ami.id == 1):
            self.ami_alice = ami
            self.ami_alice.registerEvent('UserEvent', self.user_callback)
            self.ami_alice.registerEvent('Hangup', self.hangup_callback)
            LOGGER.info("Alice AMI connected")
        elif (ami.id == 2):
            self.ami_bob = ami
            self.ami_bob.registerEvent('UserEvent', self.user_callback)
            self.ami_bob.registerEvent('Hangup', self.hangup_callback)
            LOGGER.info("Bob AMI connected")
        else:
            LOGGER.info("Unmanaged AMI ID %d received" % ami.id)

        if self.connections == self.instances:
            # We can get started with the test!
            LOGGER.info("Time to run tests!")
            self.run_tests()

    def run_tests(self):
        """Run the next test"""
        if self.current_run < len(self.test_runs):
            LOGGER.info("Executing test %d" % self.current_run)
            self.reset_timeout()
            self.uut_alice_channel = None
            self.uut_bob_channel = None
            self.start_test(self.test_runs[self.current_run])
        elif self.current_run == len(self.test_runs):
            LOGGER.info("All calls executed, stopping")
            self.remove_fail_token(self.bridge_fail_token)
            self.set_passed(True)
            self.stop_reactor()

    def start_test(self, test_run):
        """Start a test run"""
        # Step 0: Set up event handlers and initialize values for this test run
        self.hangup = test_run['hangup'] if 'hangup' in test_run else None
        self.features = test_run['features'] if 'features' in test_run else []
        self.alice_channel = None
        self.bob_channel = None
        self.uut_alice_channel = None
        self.uut_bob_channel = None
        self.uut_bridge_id = None
        self.alice_hungup = False
        self.bob_hungup = False
        self.uut_alice_hungup = False
        self.uut_bob_hungup = False
        self.current_feature = 0
        self.infeatures = False
        self.issue_hangups_on_bridged = False
        self.bridged = False

        # Step 1: Initiate a call from Alice to Bob
        LOGGER.info("Originating call")
        self.ami_alice.originate(
            channel=test_run['originate_channel'],
            exten='test_call', context='default', priority='1',
            variable={
                'TALK_AUDIO': os.path.join(os.getcwd(), 'lib/python/asterisk/audio')
            })

    def user_callback(self, ami, event):
        """UserEvent AMI event callback"""

        if (event.get('userevent') == 'Connected'):
            if ami is self.ami_bob:
                self.bob_channel = event.get('channel')
                LOGGER.info("Bob's channel is %s" % self.bob_channel)
            elif ami is self.ami_alice:
                self.alice_channel = event.get('channel')
                LOGGER.info("Alice's channel is %s" % self.alice_channel)

        if (event.get('userevent') == 'TalkDetect'):
            if event.get('result') == 'pass':
                msg = "Two way audio properly detected between Bob and Alice"
                LOGGER.info(msg)
                self.audio_detected = True
                self.check_identities(
                    alice_connected_line=BridgeTestCase.ALICE_CONNECTED,
                    bob_connected_line=BridgeTestCase.BOB_CONNECTED,
                    bob_bridge_peer=self.uut_alice_channel,
                    alice_bridge_peer=self.uut_bob_channel)
            else:
                LOGGER.warning("Audio issues on bridged call")
                self.stop_reactor()
        return (ami, event)

    def hangup_callback(self, ami, event):
        """Hangup AMI event callback"""

        if ami is self.ami_bob and event.get('channel') == self.bob_channel:
            LOGGER.info("Bob has hung up")
            self.bob_hungup = True
        elif (ami is self.ami_alice and
              event.get('channel') == self.alice_channel):
            LOGGER.info("Alice has hung up")
            self.alice_hungup = True
        elif ami is self.ami_uut:
            if event.get('channel') == self.uut_alice_channel:
                LOGGER.info("UUT Alice hang up")
                self.uut_alice_hungup = True
            elif event.get('channel') == self.uut_bob_channel:
                LOGGER.info("UUT Bob hang up")
                self.uut_bob_hungup = True
        else:
            LOGGER.debug('Passing on Hangup for %s' % event['channel'])

        if (self.bob_hungup and self.alice_hungup and
                self.uut_alice_hungup and self.uut_bob_hungup):
            for callback in self.call_end_observers:
                callback(self.ami_uut, self.ami_alice, self.ami_bob)
            # Test call has concluded move on!
            self.current_run += 1
            self.run_tests()
        return (ami, event)

    def uut_bridge_create_callback(self, ami, event):
        """BridgeCreate AMI event callback from UUT instance

        This event only applies to Asterisk 12 and later.
        """

        LOGGER.debug('Bridge ID: %s' % event.get('bridgeuniqueid'))
        self.uut_bridge_id = event.get('bridgeuniqueid')
        return (ami, event)

    def uut_bridge_enter_callback(self, ami, event):
        """BridgeEnter AMI event callback from UUT instance

        This event only applies to Asterisk 12 and later.
        """

        if self.uut_bridge_id != event.get('bridgeuniqueid'):
            return

        LOGGER.debug('Bridge ID: %s' % event.get('bridgeuniqueid'))
        channel = event.get('channel')

        if 'alice' in channel and self.uut_alice_channel is None:
            self.uut_alice_channel = channel
            LOGGER.info('UUT Alice Channel: %s' % self.uut_alice_channel)
        elif 'bob' in channel and self.uut_bob_channel is None:
            self.uut_bob_channel = channel
            LOGGER.info('UUT Bob Channel: %s' % self.uut_bob_channel)
            LOGGER.debug("Bridge is up between %s and %s"
                         % (self.uut_alice_channel, self.uut_bob_channel))
            LOGGER.debug("Type of bridge is %s" % event.get('bridgetype'))
            self.bridged = True
            if self.issue_hangups_on_bridged:
                self.send_hangup()
        return (ami, event)

    def uut_bridge_leave_callback(self, ami, event):
        """BridgeLeave AMI event callback from UUT instance

        This event only applies to Asterisk 12 and later.
        """

        LOGGER.debug('Bridge ID: %s' % event.get('bridgeuniqueid'))
        LOGGER.debug("Bridge is down")
        self.bridged = False
        return (ami, event)

    def uut_bridge_callback(self, ami, event):
        """Bridge AMI event callback from UUT instance

        This event only applies to Asterisk 11 and earlier.
        """

        if self.uut_alice_channel is None:
            self.uut_alice_channel = event.get('channel1')
            LOGGER.info('UUT Alice Channel: %s' % self.uut_alice_channel)
        if self.uut_bob_channel is None:
            self.uut_bob_channel = event.get('channel2')
            LOGGER.info('UUT Bob Channel: %s' % self.uut_bob_channel)
        if event.get('bridgestate') == 'Link':
            LOGGER.debug("Bridge is up between %s and %s"
                         % (event.get('channel1'), event.get('channel2')))
            LOGGER.debug("Type of bridge is %s" % event.get('bridgetype'))
            self.bridged = True
            if self.issue_hangups_on_bridged:
                self.send_hangup()
        else:
            LOGGER.debug("Bridge is down")
            self.bridged = False
        return (ami, event)

    def check_identities(self, alice_connected_line=None,
                         bob_connected_line=None,
                         alice_bridge_peer=None,
                         bob_bridge_peer=None):
        """Check the identities of Alice & Bob

        Keyword Arguments:
        alice_connected_line The expected connected line value for Alice.
                             Default is None
        bob_connected_line   The expected connected line value for Bob. Default
                             is None
        alice_bridge_peer    The expected bridge peer for Alice. Default is None
        bob_bridge_peer      The expected bridge peer for Bob. Default is None

        Note: setting any parameter to None will cause it to not be checked
        """

        def alice_connected(value, expected):
            """Handle alice connected line"""
            LOGGER.info("Alice's Connected line is %s" % value)
            if value != expected:
                LOGGER.warning("Bad Connected line value for Alice: expected "
                               "%s, actual %s" % (expected, value))
                self.set_passed(False)

        def bob_connected(value, expected):
            """Handle bob connected line"""
            LOGGER.info("Bob's Connected line is %s" % value)
            if value != expected:
                LOGGER.warning("Bad Connected line value for Bob: expected %s, "
                               "actual %s" % (expected, value))
                self.set_passed(False)

        def alice_bridgepeer(value, expected):
            """Handle alice BRIDGEPEER variable"""
            LOGGER.info("Alice's BRIDGEPEER is %s" % value)
            if value != expected:
                LOGGER.warning("Bad BRIDGEPEER value for Alice: expected %s, "
                               "actual %s" % (expected, value))
                self.set_passed(False)

        def bob_bridgepeer(value, expected):
            """Handle bob BRIDGEPEER variable"""
            LOGGER.info("Bob's BRIDGEPEER is %s" % value)
            if value != expected:
                LOGGER.warning("Bad BRIDGEPEER value for Bob: expected %s, "
                               "actual %s" % (expected, value))
                self.set_passed(False)
            self.execute_features()

        if alice_connected_line is not None:
            self.ami_uut.getVar(
                self.uut_alice_channel,
                'CONNECTEDLINE(all)').addCallback(alice_connected,
                                                  alice_connected_line)
        if bob_connected_line is not None:
            self.ami_uut.getVar(
                self.uut_bob_channel,
                'CONNECTEDLINE(all)').addCallback(bob_connected,
                                                  bob_connected_line)
        if alice_bridge_peer is not None:
            self.ami_uut.getVar(
                self.uut_alice_channel,
                'BRIDGEPEER').addCallback(alice_bridgepeer, alice_bridge_peer)
        if bob_bridge_peer is not None:
            self.ami_uut.getVar(
                self.uut_bob_channel,
                'BRIDGEPEER').addCallback(bob_bridgepeer, bob_bridge_peer)

    def execute_features(self):
        """Execute the next feature for this test"""

        if self.current_feature < len(self.features):
            self.infeatures = True
            self.reset_timeout()
            LOGGER.info("Going to execute a feature")
            self.execute_feature(self.features[self.current_feature])
        else:
            LOGGER.info("All features executed")
            self.ami_uut.userEvent("features_executed")
            self.send_hangup()

    def execute_feature(self, feature):
        """Execute the specified feature"""

        if (not 'who' in feature
                or not 'what' in feature
                or not 'success' in feature):
            LOGGER.warning("Missing necessary feature information")
            self.set_passed(False)
        if feature['who'] == 'alice':
            ami = self.ami_alice
            channel = self.alice_channel
        elif feature['who'] == 'bob':
            ami = self.ami_bob
            channel = self.bob_channel
        else:
            LOGGER.warning("Feature target must be 'alice' or 'bob'")
            self.set_passed(False)

        if feature['what'] not in BridgeTestCase.FEATURE_MAP:
            LOGGER.warning("Unknown feature requested")
            self.set_passed(False)

        if feature['success'] == 'true':
            self.feature_success = True
        else:
            self.feature_success = False

        for observer in self.feature_start_observers:
            observer(self, self.features[self.current_feature])

        LOGGER.info("Sending feature %s from %s" % (feature['what'], feature['who']))
        # make sure to put a gap between DTMF digits to ensure that events
        # headed to the UUT are not ignored because they occur too quickly
        sleep(0.25)
        ami.playDTMF(channel, BridgeTestCase.FEATURE_MAP[feature['what']])
        sleep(0.25)

        if ((feature['what'] == 'blindxfer' or feature['what'] == 'atxfer')
                and 'exten' in feature):
            # playback the extension requested
            for digit in list(feature['exten']):
                sleep(0.25)
                ami.playDTMF(channel, digit)
                sleep(0.25)

    def test_callback(self, ami, event):
        """TestEvent AMI event callback"""

        if event.get('state') != 'FEATURE_DETECTION':
            return

        if not self.infeatures:
            # We don't care about features yet, so
            # just return
            return

        LOGGER.info("Got FEATURE_DETECTION event")
        if event.get('result') == 'success':
            LOGGER.info("Feature detected was %s" % event.get('feature'))
            if not self.feature_success:
                LOGGER.warning("Feature succeeded when failure expected")
                self.set_passed(False)
            elif (self.features[self.current_feature]['what'] !=
                    event.get('feature')):
                LOGGER.warning("Unexpected feature triggered")
                self.set_passed(False)
        else:
            LOGGER.info("No feature detected")
            if self.feature_success:
                LOGGER.warning("Feature failed when success was expected")
                self.set_passed(False)
        for observer in self.feature_end_observers:
            observer(self, self.features[self.current_feature])
        # Move onto the next feature!
        self.current_feature += 1
        self.execute_features()
        return (ami, event)

    def send_hangup(self):
        """Send hangup to the channel specified by self.hangup"""
        if not self.hangup:
            LOGGER.info("No hangup set. Hang up will happen externally")
            return

        if not self.bridged:
            LOGGER.info("Delaying hangup until call is re-bridged")
            self.issue_hangups_on_bridged = True
            return

        LOGGER.info("Sending a hangup to %s" % self.hangup)
        if self.hangup == 'alice':
            ami = self.ami_alice
            channel = self.alice_channel
        elif self.hangup == 'bob':
            ami = self.ami_bob
            channel = self.bob_channel
        else:
            raise Exception("Invalid hangup target specified: %s" % self.hangup)

        ami.hangup(channel)

    def register_call_end_observer(self, callback):
        """Register an observer to be called when a call ends

        The callback should take three parameters:
        (1) The AMI instance for the UUT
        (2) The AMI instance for Alice
        (3) The AMI instance for Bob
        """

        self.call_end_observers.append(callback)
