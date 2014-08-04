#!/usr/bin/env python
"""Generic pluggable modules

Copyright (C) 2012, Digium, Inc.
Kinsey Moore <kmoore@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
"""
import os
import sys
import logging
import shutil

sys.path.append("lib/python")
from ami import AMIEventInstance
from twisted.internet import reactor
from starpy import fastagi

LOGGER = logging.getLogger(__name__)

class Originator(object):
    """Pluggable module class that originates calls in Asterisk"""

    def __init__(self, module_config, test_object):
        """Initialize config and register test_object callbacks."""
        self.ami = None
        test_object.register_ami_observer(self.ami_connect)
        self.test_object = test_object
        self.current_destination = 0
        self.ami_callback = None
        self.scenario_count = 0
        self.config = {
            'channel': 'Local/s@default',
            'application': 'Echo',
            'data': '',
            'context': '',
            'exten': '',
            'priority': '',
            'ignore-originate-failure': 'no',
            'trigger': 'scenario_start',
            'scenario-trigger-after': None,
            'scenario-name': None,
            'id': '0',
            'account': None,
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
            if (self.config['scenario-trigger-after'] is not None and
                    self.config['scenario-name'] is not None):
                LOGGER.error("Conflict between 'scenario-trigger-after' and "
                             "'scenario-name'. Only one may be used.")
                raise Exception
            else:
                test_object.register_scenario_started_observer(
                    self.scenario_started)
        elif self.config['trigger'] == 'event':
            if not self.config['event']:
                LOGGER.error("Event specifier for trigger type 'event' is "
                             "missing")
                raise Exception

            # set id to the AMI id for the origination if it is unset
            if 'id' not in self.config['event']:
                self.config['event']['id'] = self.config['id']

            callback = AMIPrivateCallbackInstance(self.config['event'],
                                                  test_object,
                                                  self.originate_callback)
            self.ami_callback = callback
        return

    def ami_connect(self, ami):
        """Handle new AMI connections."""
        LOGGER.info("AMI %s connected", str(ami.id))
        if str(ami.id) == self.config['id']:
            self.ami = ami
            if self.config['trigger'] == 'ami_connect':
                self.originate_call()
        return

    def failure(self, result):
        """Handle origination failure."""

        if self.config['ignore-originate-failure'] == 'no':
            LOGGER.info("Originate failed: %s", str(result))
            self.test_object.set_passed(False)
        return None

    def originate_callback(self, ami, event):
        """Handle event callbacks."""
        LOGGER.info("Got event callback for Origination")
        self.originate_call()
        return True

    def originate_call(self):
        """Originate the call"""
        LOGGER.info("Originating call")

        defer = None
        if len(self.config['context']) > 0:
            defer = self.ami.originate(channel=self.config['channel'],
                                       context=self.config['context'],
                                       exten=self.config['exten'],
                                       priority=self.config['priority'],
                                       timeout=self.config['timeout'],
                                       account=self.config['account'],
                                       async=self.config['async'])
        else:
            defer = self.ami.originate(channel=self.config['channel'],
                                       application=self.config['application'],
                                       data=self.config['data'],
                                       timeout=self.config['timeout'],
                                       account=self.config['account'],
                                       async=self.config['async'])
        defer.addErrback(self.failure)

    def scenario_started(self, result):
        """Handle origination on scenario start if configured to do so."""
        LOGGER.info("Scenario '%s' started", result.name)
        if self.config['scenario-name'] is not None:
            if result.name == self.config['scenario-name']:
                LOGGER.debug("Scenario name '%s' matched", result.name)
                self.originate_call()
        elif self.config['scenario-trigger-after'] is not None:
            self.scenario_count += 1
            trigger_count = int(self.config['scenario-trigger-after'])
            if self.scenario_count == trigger_count:
                LOGGER.debug("Scenario count has been met")
                self.originate_call()
        else:
            self.originate_call()
        return result


class AMIPrivateCallbackInstance(AMIEventInstance):
    """Subclass of AMIEventInstance that operates by calling a user-defined
    callback function. The callback function returns the current disposition
    of the test (i.e. whether the test is currently passing or failing).
    """

    def __init__(self, instance_config, test_object, callback):
        """Constructor"""
        super(AMIPrivateCallbackInstance, self).__init__(instance_config,
                                                         test_object)
        self.callback = callback
        if 'start' in instance_config:
            self.passed = True if instance_config['start'] == 'pass' else False

    def event_callback(self, ami, event):
        """Generic AMI event handler"""
        self.passed = self.callback(ami, event)
        return (ami, event)

    def check_result(self, callback_param):
        """Set the test status based on the result of self.callback"""
        self.test_object.set_passed(self.passed)
        return callback_param


class AMIChannelHangup(AMIEventInstance):
    """An AMIEventInstance derived class that hangs up a channel when an
    event is matched."""

    def __init__(self, instance_config, test_object):
        """Constructor for pluggable modules"""
        super(AMIChannelHangup, self).__init__(instance_config, test_object)
        self.hungup_channel = False
        self.delay = instance_config.get('delay') or 0

    def event_callback(self, ami, event):
        """Override of the event callback"""
        if self.hungup_channel:
            return
        if 'channel' not in event:
            return
        LOGGER.info("Hanging up channel %s", event['channel'])
        self.hungup_channel = True
        reactor.callLater(self.delay, ami.hangup, event['channel'])
        return (ami, event)


class AMIChannelHangupAll(AMIEventInstance):
    """An AMIEventInstance derived class that hangs up all the channels when
    an event is matched."""

    def __init__(self, instance_config, test_object):
        """Constructor for pluggable modules"""
        super(AMIChannelHangupAll, self).__init__(instance_config, test_object)
        test_object.register_ami_observer(self.__ami_connect)
        self.channels = []

    def __ami_connect(self, ami):
        """AMI connect handler"""
        if str(ami.id) in self.ids:
            ami.registerEvent('Newchannel', self.__new_channel_handler)
            ami.registerEvent('Hangup', self.__hangup_handler)

    def __new_channel_handler(self, ami, event):
        """New channel event handler"""
        self.channels.append({'id': ami.id, 'channel': event['channel']})

    def __hangup_handler(self, ami, event):
        """Hangup event handler"""
        objects = [x for x in self.channels if
                   (x['id'] == ami.id and
                    x['channel'] == event['channel'])]
        for obj in objects:
            self.channels.remove(obj)

    def event_callback(self, ami, event):
        """Override of the event callback"""
        def __hangup_ignore(result):
            """Ignore hangup errors"""
            # Ignore hangup errors - if the channel is gone, we don't care
            return result

        objects = [x for x in self.channels if x['id'] == ami.id]
        for obj in objects:
            LOGGER.info("Hanging up channel %s", obj['channel'])
            ami.hangup(obj['channel']).addErrback(__hangup_ignore)
            self.channels.remove(obj)


class HangupMonitor(object):
    """A class that monitors for new channels and hungup channels. When all
    channels it has monitored for have hung up, it ends the test.

    Essentially, as long as there are new channels it will keep the test
    going; however, once channels start hanging up it will kill the test
    on the last hung up channel.
    """

    def __init__(self, instance_config, test_object):
        """Constructor for pluggable modules"""
        super(HangupMonitor, self).__init__()
        self.config = instance_config
        self.test_object = test_object
        self.test_object.register_ami_observer(self.__ami_connect)
        self.channels = []
        self.num_calls = 0

    def __ami_connect(self, ami):
        """AMI connect handler"""
        if str(ami.id) in self.config["ids"]:
            ami.registerEvent('Newchannel', self.__new_channel_handler)
            ami.registerEvent('Hangup', self.__hangup_handler)

    def __new_channel_handler(self, ami, event):
        """Handler for the Newchannel event"""
        LOGGER.debug("Tracking channel %s", event['channel'])
        self.channels.append(event['channel'])
        return (ami, event)

    def __hangup_handler(self, ami, event):
        """Handler for the Hangup event"""
        LOGGER.debug("Channel %s hungup", event['channel'])
        self.channels.remove(event['channel'])
        self.num_calls += 1
        if 'min_calls' in self.config\
            and self.num_calls < self.config["min_calls"]:
            return (ami, event)
        if len(self.channels) == 0:
            LOGGER.info("All channels have hungup; stopping test")
            self.stop_test()
        return (ami, event)

    def stop_test(self):
        """Allow subclasses to take different actions to stop the test."""
        self.test_object.stop_reactor()


class CallFiles(object):
    """ This class allows call files to be created from a YAML configuration"""
    def __init__(self, instance_config, test_object):
        """Constructor"""
        super(CallFiles, self).__init__()
        self.test_object = test_object
        self.call_file_instances = instance_config
        self.locale = ""

        if self.call_file_instances:
            self.test_object.register_ami_observer(self.ami_connect)
        else:
            LOGGER.error("No configuration was specified for call files")
            self.test_failed()

    def test_failed(self):
        """Checks to see whether or not the call files were
           correctly specified """
        self.test_object.set_passed(False)
        self.test_object.stop_reactor()

    def write_call_file(self, call_file_num, call_file):
        """Write out the specified call file

        Keyword Parameters:
        call_file_num Which call file in the test we're writing out
        call_file     A dictionary containing the call file
                      information, derived from the YAML
        """
        params = call_file.get('call-file-params')
        if not params:
            LOGGER.error("No call file parameters specified")
            self.test_failed()
            return

        self.locale = ("%s%s/tmp/test%d.call" %
                       (self.test_object.ast[int(call_file['id'])].base,
                        self.test_object.ast[int(call_file['id'])].directories
                        ["astspooldir"], call_file_num))

        with open(self.locale, 'w') as outfile:
            for key, value in params.items():
                outfile.write("%s: %s\n" % (key, value))
        LOGGER.debug("Wrote call file to %s", self.locale)
        self.move_file(call_file_num, call_file)

    def ami_connect(self, ami):
        """Handler for AMI connection """
        for index, call_file in enumerate(self.call_file_instances):
            if ami.id == int(call_file.get('id')):
                self.write_call_file(index, call_file)

    def move_file(self, call_file_num, call_file):
        """Moves call files to astspooldir directory to be run """
        src_file = self.locale
        dst_file = ("%s%s/outgoing/test%s.call" %
                    (self.test_object.ast[int(call_file['id'])].base,
                     self.test_object.ast[int(call_file['id'])].directories
                     ["astspooldir"], call_file_num))

        LOGGER.info("Moving file %s to %s", src_file, dst_file)

        shutil.move(src_file, dst_file)
        os.utime(dst_file, None)

class FastAGIModule(object):
    """A class that makes a FastAGI server available to be called via the
    dialplan and allows simple commands to be executed.

    Configuration is as follows:
    config-section:
        host: '127.0.0.1'
        port: 4573
        commands:
            - 'SET VARIABLE "CHANVAR1" "CHANVAL1"'

    Instead of commands, a callback may be specified to interact with Asterisk:
        callback:
            module: fast_agi_callback_module
            method: fast_agi_callback_method
    """

    def __init__(self, instance_config, test_object):
        """Constructor for pluggable modules"""
        super(FastAGIModule, self).__init__()
        self.test_object = test_object
        self.port = instance_config.get('port', 4573)
        self.host = instance_config.get('host', '127.0.0.1')
        self.commands = instance_config.get('commands')
        if 'callback' in instance_config:
            self.callback_module = instance_config['callback']['module']
            self.callback_method = instance_config['callback']['method']
        fastagi_factory = fastagi.FastAGIFactory(self.fastagi_connect)
        reactor.listenTCP(self.port, fastagi_factory,
                          test_object.reactor_timeout, self.host)

    def fastagi_connect(self, agi):
        """Handle incoming connections"""
        if self.commands:
            return self.execute_command(agi, 0)
        else:
            callback_module = __import__(self.callback_module)
            method = getattr(callback_module, self.callback_method)
            method(self.test_object, agi)

    def on_command_failure(self, reason, agi, idx):
        """Failure handler for executing commands"""
        LOGGER.error('Could not execute command %s: %s',
                     idx, self.commands[idx])
        LOGGER.error(reason.getTraceback())
        agi.finish()

    def on_command_success(self, result, agi, idx):
        """Handler for executing commands"""
        LOGGER.debug("Successfully executed '%s': %s",
                     self.commands[idx], result)
        self.execute_command(agi, idx + 1)

    def execute_command(self, agi, idx):
        """Execute the requested command"""
        if len(self.commands) <= idx:
            LOGGER.debug("Completed all commands for %s:%s",
                         self.host, self.port)
            agi.finish()
            return

        agi.sendCommand(self.commands[idx])\
	.addCallback(self.on_command_success, agi, idx)\
	.addErrback(self.on_command_failure, agi, idx)
