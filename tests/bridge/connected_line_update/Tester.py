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

LOGGER = logging.getLogger(__name__)

class Tester(object):
    def __init__(self, module_config, test_object):
        self.alice = None
        self.bob = None
        test_object.register_ami_observer(self.ami_connect)
        self.alice_channel = None
        self.bob_channel = None
        return

    def ami_connect(self, ami):
        if ami.id == 0:
            ami.registerEvent('UserEvent', self.uut_userevent)
        elif ami.id == 1:
            self.alice = ami
            self.alice.registerEvent('Newchannel', self.alice_newchannel)
        elif ami.id == 2:
            self.bob = ami
            self.bob.registerEvent('Newchannel', self.bob_newchannel)

    def alice_newchannel(self, ami, event):
        '''Capture originated channel on Alice.'''
        self.alice_channel = event['channel']

    def bob_newchannel(self, ami, event):
        '''Capture incoming channel on Bob.'''
        self.bob_channel = event['channel']

    def uut_userevent(self, ami, event):
        '''Handle UserEvents from UUT'''

        LOGGER.info('Got UUT event: %s' % str(event))
        # wait until both are connected to process events
        if event['userevent'] == 'CLInfo':
            # first update
            if event['clinfo'] == 'newbob <2345>':
                LOGGER.info('Received first connected line update')
                self.bob_to_alice_update()
            # second update
            elif event['clinfo'] == 'newalice <5432>':
                LOGGER.info('Received second connected line update')
                # tear down the call
                self.alice.hangup(self.alice_channel)
        elif event['userevent'] == 'features_executed':
            self.alice_to_bob_update()

    def alice_to_bob_update(self):
        '''When Alice and Bob first indicate connectivity, kick off the first update.'''
        self.alice.setVar(self.alice_channel, 'CONNECTEDLINE(all)', 'newbob <2345>')
        LOGGER.info('Set new CLI on alice to propagate to bob')

    def bob_to_alice_update(self):
        '''After the first update is successfully passed across, kick off the second update.'''
        self.bob.setVar(self.bob_channel, 'CONNECTEDLINE(all)', 'newalice <5432>')
        LOGGER.info('Set new CLI on bob to propagate to alice')
