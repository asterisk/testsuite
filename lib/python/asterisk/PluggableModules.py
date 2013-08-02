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
from ami import AMIEventInstance

LOGGER = logging.getLogger(__name__)

class Originator(object):
    def __init__(self, module_config, test_object):
        '''Initialize config and register test_object callbacks.'''
        self.ami = None
        test_object.register_ami_observer(self.ami_connect)
        self.test_object = test_object
        self.current_destination = 0
        self.ami_callback = None
        self.config = {
            'channel': 'Local/s@default',
            'application': 'Echo',
            'data': '',
            'context': '',
            'exten': '',
            'priority': '',
            'ignore-originate-failure': 'no',
            'trigger': 'scenario_start',
            'id': '0',
            'async': 'False',
            'event': None,
            'timeout': None,
        }

        # process config
        if not module_config:
            return
        for k in module_config.keys():
            if k in self.config:
                self.config[k] = module_config[k]

        if self.config['trigger'] == 'scenario_start':
            test_object.register_scenario_started_observer(self.scenario_started)
        elif self.config['trigger'] == 'event':
            if not self.config['event']:
                LOGGER.error("Event specifier for trigger type 'event' is missing")
                raise Exception

            # set id to the AMI id for the origination if it is unset
            if 'id' not in self.config['event']:
                self.config['event']['id'] = self.config['id']

            self.ami_callback = AMIPrivateCallbackInstance(self.config['event'], test_object, self.originate_callback)
        return

    def ami_connect(self, ami):
        '''Handle new AMI connections.'''
        LOGGER.info("AMI %s connected" % (str(ami.id)))
        if str(ami.id) == self.config['id']:
            self.ami = ami
            if self.config['trigger'] == 'ami_connect':
                self.originate_call()
        return

    def failure(self, result):
        '''Handle origination failure.'''

        if self.config['ignore-originate-failure'] == 'no':
            LOGGER.info("Originate failed: %s" % (str(result)))
            self.test_object.set_passed(False)
        return None

    def originate_callback(self, ami, event):
        '''Handle event callbacks.'''
        LOGGER.info('Got event callback')
        self.originate_call()
        return True

    def originate_call(self):
        '''Handle origination of the call based on the options provided in the configuration.'''
        LOGGER.info("Originating call")

        if len(self.config['context']) > 0:
            self.ami.originate(channel=self.config['channel'],
                               context=self.config['context'],
                               exten=self.config['exten'],
                               priority=self.config['priority'],
                               timeout=self.config['timeout'],
                               async=self.config['async']).addErrback(self.failure)
        else:
            self.ami.originate(channel=self.config['channel'],
                               application=self.config['application'],
                               data=self.config['data'],
                               timeout=self.config['timeout'],
                               async=self.config['async']).addErrback(self.failure)

    def scenario_started(self, result):
        '''Handle origination on scenario start if configured to do so.'''
        LOGGER.info("Scenario started")
        self.originate_call()
        return result


class AMIPrivateCallbackInstance(AMIEventInstance):
    '''
    Subclass of AMIEventInstance that operates by calling a user-defined
    callback function. The callback function returns the current disposition
    of the test (i.e. whether the test is currently passing or failing).
    '''
    def __init__(self, instance_config, test_object, callback):
        super(AMIPrivateCallbackInstance, self).__init__(instance_config, test_object)
        self.callback = callback
        if 'start' in instance_config:
            self.passed = True if instance_config['start'] == 'pass' else False

    def event_callback(self, ami, event):
        self.passed = self.callback(ami, event)

    def check_result(self, callback_param):
        self.test_object.set_passed(self.passed)
        return callback_param


class AMIChannelHangup(AMIEventInstance):
    ''' An AMIEventInstance derived class that hangs up a channel when an
    event is matched. '''

    def __init__(self, instance_config, test_object):
        ''' Constructor for pluggable modules '''
        super(AMIChannelHangup, self).__init__(instance_config, test_object)
        self.hungup_channel = False

    def event_callback(self, ami, event):
        ''' Override of the event callback '''
        if self.hungup_channel:
            return
        if 'channel' not in event:
            return
        LOGGER.info('Hanging up channel %s' % event['channel'])
        self.hungup_channel = True
        ami.hangup(event['channel'])


class AMIChannelHangupAll(AMIEventInstance):
    ''' An AMIEventInstance derived class that hangs up all the channels when
    an event is matched. '''

    def __init__(self, instance_config, test_object):
        ''' Constructor for pluggable modules '''
        super(AMIChannelHangupAll, self).__init__(instance_config, test_object)
        test_object.register_ami_observer(self.__ami_connect)
        self.channels = []

    def __ami_connect(self, ami):
        if str(ami.id) in self.ids:
            ami.registerEvent('Newchannel', self.__new_channel_handler)
            ami.registerEvent('Hangup', self.__hangup_handler)

    def __new_channel_handler(self, ami, event):
        self.channels.append({'id': ami.id, 'channel': event['channel']})

    def __hangup_handler(self, ami, event):
        objects = [x for x in self.channels if x['id'] == ami.id and x['channel'] == event['channel']]
        for obj in objects:
            self.channels.remove(obj)

    def event_callback(self, ami, event):
        ''' Override of the event callback '''
        def __hangup_ignore(result):
            # Ignore hangup errors - if the channel is gone, we don't care
            return

        objects = [x for x in self.channels if x['id'] == ami.id]
        for obj in objects:
            LOGGER.info('Hanging up channel %s' % obj['channel'])
            ami.hangup(obj['channel']).addErrback(__hangup_ignore)
            self.channels.remove(obj)
