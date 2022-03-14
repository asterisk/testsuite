#!/usr/bin/env python
'''
Copyright (C) 2013, Digium, Inc.
Matt Jordan <mjordan@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
'''

import logging

LOGGER = logging.getLogger(__name__)

class BridgeAction(object):
    ''' Pluggable Module object that manipulates channels
    using the Bridge AMI action
    '''

    def __init__(self, module_config, test_object):
        ''' Constructor

        :param module_config This object's YAML derived configuration
        :param test_object The test object it plugs onto
        '''
        self.test_object = test_object
        self.test_object.register_ami_observer(self._ami_connected_handler)
        self.test_object.register_stop_observer(self._stop_handler)
        self.channels = []
        self.originate = 1
        self.round = 1
        self.ami = None
        self.channel_state = {}
        self.expected_events = {
            'channel_0_1_bridged': False,
            'channel_2_3_bridged': False,
            'channel_3_4_bridged': False,
            'channel_1_3_bridged': False, }

    def _ami_connected_handler(self, ami):
        ''' AMI connected handler

        :param The AMI instance that just connected
        '''
        self.ami = ami
        ami.registerEvent('Newexten', self._new_exten_handler)
        ami.registerEvent('BridgeEnter', self._bridge_enter_handler)
        ami.registerEvent('BridgeLeave', self._bridge_leave_handler)
        ami.registerEvent('Newchannel', self._new_channel_handler)

        # Originate some channels
        LOGGER.debug('Originating channels')
        ami.originate(channel='Local/waiting_area@default',
                      context='default',
                      exten='waiting_area',
                      priority=1,
                      nowait=True).addErrback(self.test_object.
                                             handle_originate_failure)

    def _new_channel_handler(self, ami, event):
        ''' AMI Newchannel event handler

        :param ami The AMI instance that the event was received from
        :param event The AMI Newchannel event

        Wait until the new channel event has been received before
        creating the next channel.
        '''
        if (';2' in event['channel'] and self.originate < 5):
            self.originate += 1
            ami.originate(channel='Local/waiting_area@default',
                          context='default',
                          exten='waiting_area',
                          priority=1,
                          nowait=True).addErrback(self.test_object.
                                                 handle_originate_failure)

    def _stop_handler(self, result):
        ''' A deferred callback called as a result of the test stopping

        :param result The deferred parameter passed from callback to callback
        '''
        failed_results = [key for key, value in self.expected_events.items()
            if not value]
        if len(failed_results) == 0:
            self.test_object.set_passed(True)
        else:
            self.test_object.set_passed(False)
            for failure in failed_results:
                LOGGER.error('Expected event {%s} did not occur!' % failure)
        return result

    def _new_exten_handler(self, ami, event):
        ''' AMI Newexten event handler

        :param ami The AMI instance that the event was received from
        :param event The AMI Newexten event

        Wait until all of the ;2 Local channels are in their Echo
        applications, then steal them and throw them into Bridges
        '''
        if ';2' not in event['channel']:
            return
        if event.get('application') != 'Echo':
            return
        LOGGER.debug('Tracking channel %s' % event['channel'])
        self.channels.append(event['channel'])
        if len(self.channels) == 5:
            self.execute_round()

    def _bridge_enter_handler(self, ami, event):
        ''' AMI BridgeEnter event handler

        :param ami The AMI instance that the event was received from
        :param event The AMI BridgeEnter event
        '''
        self.channel_state[event['channel']] = event['bridgeuniqueid']

        # Handle this round's logic
        if self.round == 1:
            if ((event['channel'] == self.channels[0] or event['channel'] == self.channels[1]) and
                self.channel_state.get(self.channels[0]) is not None and
                self.channel_state.get(self.channels[1]) is not None and
                self.channel_state.get(self.channels[0]) == self.channel_state.get(self.channels[1])):
                LOGGER.info('Channel 0 (%s) and 1 (%s) are in a bridge together' %
                    (self.channels[0], self.channels[1]))
                self.expected_events['channel_0_1_bridged'] = True
            if ((event['channel'] == self.channels[2] or event['channel'] == self.channels[3]) and
                self.channel_state.get(self.channels[2]) is not None and
                self.channel_state.get(self.channels[3]) is not None and
                self.channel_state.get(self.channels[2]) == self.channel_state.get(self.channels[3])):
                LOGGER.info('Channel 2 (%s) and 3 (%s) are in a bridge together' %
                    (self.channels[2], self.channels[3]))
                self.expected_events['channel_2_3_bridged'] = True
            if (self.expected_events['channel_0_1_bridged'] and
                self.expected_events['channel_2_3_bridged']):
                self.round = 2
                self.execute_round()
        elif self.round == 2:
            if (self.channel_state.get(self.channels[3]) is not None and
                self.channel_state.get(self.channels[4]) is not None and
                self.channel_state.get(self.channels[3]) == self.channel_state.get(self.channels[4])):
                self.expected_events['channel_3_4_bridged'] = True
                LOGGER.info('Channel 3 (%s) and 4 (%s) are in a bridge together' %
                    (self.channels[3], self.channels[4]))
                self.round = 3
                self.execute_round()
        elif self.round == 3:
            if (self.channel_state.get(self.channels[1]) is not None and
                self.channel_state.get(self.channels[3]) is not None and
                self.channel_state.get(self.channels[1]) == self.channel_state.get(self.channels[3])):
                LOGGER.info('Channel 2 (%s) and 4 (%s) are in a bridge together' %
                    (self.channels[1], self.channels[3]))
                self.expected_events['channel_1_3_bridged'] = True
                self.ami.hangup(self.channels[1])
                self.test_object.stop_reactor()

    def _bridge_leave_handler(self, ami, event):
        ''' AMI BridgeLeave event handler

        :param ami The AMI instance that the event was received from
        :param event The AMI BridgeLeave event
        '''
        self.channel_state[event['channel']] = None

    def execute_round(self):
        ''' Execute a round of the test

        This will take 4 of the Local channel halves (operating on the ;2 ends)
        and throw them into Bridges. Once all four are in two bridges, we will
        take channel #3 and Bridge it with channel #4. We will then take
        channel #1 and channel #3 and Bridge them together.

        (Round 1):  0 <-> 1      2 <-> 3
        (Round 2):  0 <-> 1      3 <-> 4
        (Round 3):  1 <-> 3

        This results in:
         * Bridges formed as a result of yanking (channels in dialplan)
         * Bridges formed from a channel in a bridge and a channel in a dialplan
         * Bridges formed between channels in bridges
        '''
        if self.round == 1:
            for i in range(0, 4, 2):
                LOGGER.info('Bridging Channel %d (%s) and Channel %d (%s)' %
                    (i, self.channels[i], i + 1, self.channels[i + 1]))
                self.ami.sendMessage(message={'Action': 'Bridge',
                    'Channel1': self.channels[i],
                    'Channel2': self.channels[i + 1], })
        elif self.round == 2:
            LOGGER.info('Bridging Channel %d (%s) and Channel %d (%s)' %
                (3, self.channels[3], 4, self.channels[4]))
            self.ami.sendMessage(message={'Action': 'Bridge',
                'Channel1': self.channels[3],
                'Channel2': self.channels[4], })
        elif self.round == 3:
            LOGGER.info('Bridging Channel %d (%s) and Channel %d (%s)' %
                (1, self.channels[3], 1, self.channels[3]))
            self.ami.sendMessage(message={'Action': 'Bridge',
                'Channel1': self.channels[1],
                'Channel2': self.channels[3], })

