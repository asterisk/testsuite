#!/usr/bin/env python
'''
Copyright (C) 2013, Digium, Inc.
Matt Jordan <mjordan@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
'''

import sys
import logging

sys.path.append("lib/python")
from version import AsteriskVersion

LOGGER = logging.getLogger(__name__)

class Transfer(object):

    __singleton_instance = None

    @staticmethod
    def get_instance():
        ''' Return the singleton instance of the application test_object

        Keyword Arguments:
        path The full path to the location of the test
        test_config The test's YAML configuration object
        '''
        if (Transfer.__singleton_instance is None):
            # Note that the constructor sets the singleton instance.
            # This is a tad backwards, but is needed for the pluggable
            # framework. If we get a get_instance call before its been set,
            # blow up - that really shouldn't ever happen
            raise Exception()
        return Transfer.__singleton_instance

    def __init__(self, module_config, test_object):
        ''' Constructor

        Keyword Arguments:
        module_config The module configuration
        test_object The test object. Must be of type BridgeTestCase
        '''
        self.module_config = module_config
        self.test_object = test_object
        self._current_feature = None

        self.test_object.register_feature_start_observer(self._handle_feature_start)
        if AsteriskVersion() >= AsteriskVersion('12'):
            self.test_object.register_ami_observer(self._handle_ami_connect)
        else:
            self.test_object.register_feature_end_observer(self._handle_feature_end)

        if (Transfer.__singleton_instance == None):
            Transfer.__singleton_instance = self

    def _handle_ami_connect(self, ami):
        ''' Handle AMI connect events '''
        if (ami.id != 0):
            return
        ami.registerEvent('AttendedTransfer', self._handle_attended_transfer)

    def _handle_feature_start(self, test_object, feature):
        ''' Callback for the BridgeTestCase feature detected event

        Keyword Arguments:
        test_object The BridgeTestCase object
        feature The specific feature that was executed
        '''
        LOGGER.debug('Setting current feature to %s' % str(feature))
        self._current_feature = feature

    def _handle_feature_end(self, test_object, feature):
        ''' Callback for the BridgeTestCase feature detected event

        Keyword Arguments:
        test_object The BridgeTestCase object
        feature The specific feature that was executed
        '''
        LOGGER.debug("current_feature: %s\n" % self._current_feature)
        if self._current_feature['who'] == 'alice':
            ami = self.test_object.ami_bob
            channel = self.test_object.bob_channel
            self.test_object.check_identities(bob_connected_line='"Charlie" <5678>')
        elif self._current_feature['who'] == 'bob':
            ami = self.test_object.ami_alice
            channel = self.test_object.alice_channel
            self.test_object.check_identities(alice_connected_line='"Charlie" <5678>')
        else:
            raise Exception()
        LOGGER.info('Hanging up channel %s' % channel)
        ami.hangup(channel)

    def _handle_attended_transfer(self, ami, event):
        ''' Handle the AttendedTransfer event. Once the event has
        triggered, the call can be torn down. '''
        LOGGER.debug('ami %d: received event %s' % (ami.id, event))
        self._handle_feature_end(None, None)

    def complete_attended_transfer(self):
        '''
        Called when we've detected that the Attended Transfer should
        complete
        '''
        if self._current_feature is None:
            raise Exception()

        if self._current_feature['who'] == 'alice':
            ami = self.test_object.ami_alice
            channel = self.test_object.alice_channel
        elif self._current_feature['who'] == 'bob':
            ami = self.test_object.ami_bob
            channel = self.test_object.bob_channel
        else:
            raise Exception()
        LOGGER.info('Hanging up channel %s' % channel)
        ami.hangup(channel)



def complete_attended_transfer(ami, event):
    '''
    Callback that occurs during an attended transfer.
    This callback signals that the test should complete the attended
    transfer by hanging up the transferer.
    '''

    LOGGER.debug('ami %d: received event %s' % (ami.id, event))
    transfer = Transfer.get_instance()
    transfer.complete_attended_transfer()
    return True
