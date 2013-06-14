#!/usr/bin/env python
'''
Copyright (C) 2012, Digium, Inc.
Kinsey Moore <kmoore@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
'''

import sys
import logging
import uuid

sys.path.append("lib/python")
from TestCase import TestCase

LOGGER = logging.getLogger(__name__)

class SimpleTestCase(TestCase):
    '''The base class for extremely simple tests requiring only a spawned call
    into the dialplan where success can be reported via a user-defined AMI
    event.'''

    default_expected_events = 1

    default_channel = 'Local/100@test'

    default_application = 'Echo'

    def __init__(self, test_path = '', test_config = None):
        ''' Constructor

        Parameters:
        test_path Optional path to the location of the test directory
        test_config Optional yaml loaded object containing config information
        '''
        TestCase.__init__(self, test_path, test_config=test_config)

        self._test_runs = []
        self._current_run = 0
        self._event_count = 0
        self.expected_events = SimpleTestCase.default_expected_events
        self._tracking_channels = []
        self._ignore_originate_failures = False
        self._spawn_after_hangup = False
        self._config_path = None

        if test_config is None or 'test-iterations' not in test_config:
            # No special test configuration defined, use defaults
            self._test_runs.append({'channel': SimpleTestCase.default_channel,
                                    'application': SimpleTestCase.default_application,
                                    'variable': {'testuniqueid': '%s' % (str(uuid.uuid1()))},
                                    })
        else:
            # Use the info in the test config to figure out what we want to run
            for iteration in test_config['test-iterations']:
                iteration['variable'] = {'testuniqueid': '%s' % (str(uuid.uuid1())),}
                self._test_runs.append(iteration)
            if 'expected_events' in test_config:
                self.expected_events = test_config['expected_events']
            if 'ignore-originate-failures' in test_config:
                self._ignore_originate_failures = test_config['ignore-originate-failures']
            if 'spawn-after-hangup' in test_config:
                self._spawn_after_hangup = test_config['spawn-after-hangup']
            if 'config-path' in test_config:
                self._config_path = test_config['config-path']
        self.create_asterisk(count=1, base_configs_path=self._config_path)

    def ami_connect(self, ami):
        ''' AMI connect handler '''

        if self.expected_events != 0:
            ami.registerEvent('UserEvent', self.__event_cb)
        ami.registerEvent('Hangup', self.__hangup_cb)
        ami.registerEvent('VarSet', self.__varset_cb)

        # Kick off the test runs
        self.__start_new_call(ami)


    def __originate_call(self, ami, call_details):
        ''' Actually originate a call

        Parameters:
        ami The AMI connection object
        call_details A dictionary object containing the parameters to pass
            to the originate
        '''
        def __swallow_originate_error(result):
            return None

        # Each originate call gets tagged with the channel variable
        # 'testuniqueid', which contains a UUID as the value.  When a VarSet
        # event happens, it will contain the Asterisk channel name with the
        # unique ID we've assigned, allowing us to associate the Asterisk
        # channel name with the channel we originated
        msg = "Originating call to %s" % call_details['channel']
        if 'application' in call_details:
            msg += " with application %s" % call_details['application']
            df = ami.originate(channel = call_details['channel'],
                          application = call_details['application'],
                          variable = call_details['variable'])
        else:
            msg += " to %s@%s at %s" % (call_details['exten'],
                                        call_details['context'],
                                        call_details['priority'],)
            df = ami.originate(channel = call_details['channel'],
                          context = call_details['context'],
                          exten = call_details['exten'],
                          priority = call_details['priority'],
                          variable = call_details['variable'])
        if self._ignore_originate_failures:
            df.addErrback(__swallow_originate_error)
        else:
            df.addErrback(self.handleOriginateFailure)
        LOGGER.info(msg)


    def __varset_cb(self, ami, event):
        ''' VarSet event handler.  This event helps us tie back the channel
        name that Asterisk created with the call we just originated '''

        if (event['variable'] == 'testuniqueid'):

            if (len([chan for chan in self._tracking_channels if
                     chan['testuniqueid'] == event['value']])):
                # Duplicate event, return
                return

            # There should only ever be one match, since we're
            # selecting on a UUID
            originating_channel = [chan for chan in self._test_runs
                                   if (chan['variable']['testuniqueid']
                                       == event['value'])][0]
            self._tracking_channels.append({
                'channel': event['channel'],
                'testuniqueid': event['value'],
                'originating_channel': originating_channel})
            LOGGER.debug("Tracking originated channel %s as %s (ID %s)" % (
                originating_channel, event['channel'], event['value']))


    def __hangup_cb(self, ami, event):
        ''' Hangup Event handler.  If configured to do so, this will spawn the
        next new call '''

        candidate_channel = [chan for chan in self._tracking_channels
                             if chan['channel'] == event['channel']]
        if (len(candidate_channel)):
            LOGGER.debug("Channel %s hung up; removing" % event['channel'])
            self._tracking_channels.remove(candidate_channel[0])
            if (self._spawn_after_hangup):
                self._current_run += 1
                self.__start_new_call(ami)


    def __start_new_call(self, ami):
        ''' Kick off the next new call, or, if we've run out of calls to make,
        stop the test '''

        if (self._current_run < len(self._test_runs)):
            self.__originate_call(ami, self._test_runs[self._current_run])
        else:
            LOGGER.info("All calls executed, stopping")
            self.stop_reactor()


    def __event_cb(self, ami, event):
        ''' UserEvent callback handler.  This is the default way in which
        new calls are kicked off. '''

        if self.verify_event(event):
            self._event_count += 1
            if self._event_count == self.expected_events:
                self.passed = True
                LOGGER.info("Test ending, hanging up current channels")
                for chan in self._tracking_channels:
                    self.ami[0].hangup(chan['channel']).addCallbacks(self.hangup,
                                                                     self.hangup_error)
            else:
                self._current_run += 1
                self.__start_new_call(ami)


    def hangup(self, result):
        ''' Called when all channels are hung up'''

        LOGGER.info("Hangup complete, stopping reactor")
        self.stop_reactor()

    def hangup_error(self, result):
        ''' Called when an error occurs during a hangup '''
        # Ignore the hangup error - in this case, the channel was disposed of
        # prior to our hangup request, which is okay
        self.stop_reactor()

    def verify_event(self, event):
        ''' Virtual method used to verify values in the event. '''
        return True


    def run(self):
        TestCase.run(self)
        self.create_ami_factory()
