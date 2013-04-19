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

        if (Transfer.__singleton_instance == None):
            Transfer.__singleton_instance = self

    def _handle_feature_start(self, test_object, feature):
        ''' Callback for the BridgeTestCase feature detected event

        Keyword Arguments:
        test_object The BridgeTestCase object
        feature The specific feature that was executed
        '''
        LOGGER.debug('Setting current feature to %s' % str(feature))
        self._current_feature = feature

    def check_connected_line(self):
        ''' Check the connected line properties '''
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


def check_connected_line(ami, event):
    '''
    Callback that occurs during a blind transfer. Check the connected line
    and hangs up the channel to start the next test.
    '''

    transfer = Transfer.get_instance()
    transfer.check_connected_line()
    return True
