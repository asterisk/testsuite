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
import re

sys.path.append("lib/python")
from ami import AMIEventInstance
from twisted.internet import reactor
from starpy import fastagi
from test_runner import load_and_parse_module
from pluggable_registry import PLUGGABLE_ACTION_REGISTRY,\
    PLUGGABLE_EVENT_REGISTRY,\
    PluggableRegistry

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
        if 'min_calls' in self.config \
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


class SoundChecker(object):
    """ This class allows the user to check if a given sound file exists,
    whether a sound file fits within a range of file size, and has enough
    energy in it to pass a BackgroundDetect threshold of silence"""

    def __init__(self, module_config, test_object):
        """Constructor"""
        super(SoundChecker, self).__init__()
        self.test_object = test_object
        self.module_config = module_config['sound-file-config']
        self.filepath = ""
        self.sound_file = {}
        self.actions = []
        self.index = 0
        self.action_index = 0
        self.auto_stop = module_config.get('auto-stop', False)
        self.test_object.register_ami_observer(self.ami_connect)

    def build_sound_file_location(self, filename, path_type, path_name=""):
        """Creates the filepath for the given sound file.
        File_path_types should include relative and absolute, and if absolute,
        look for an absolute_path string. Fails if the path type is invalid
        or parameters are missing

        Keyword Arguments:
        filename:  The same of the file to be set and used
        path-type: The type of path file- either relative or absolute
        path_name: Optional parameter that must be included with an
                   absolute type_path. It stores the actual file path to be
                   used
        returns:
        filepath: The filepath that this sound_file test will use.
        """
        asterisk_instance = self.module_config[self.index].get('id', 0)
        if path_type == 'relative':
            ast_instance = self.test_object.ast[asterisk_instance]
            base_path = ast_instance.base
            spool_dir = ast_instance.directories["astspooldir"]
            filepath = ("%s%s/%s" % (base_path, spool_dir, filename))
            return filepath
        elif path_type == 'absolute':
            if path_name:
                filepath = "%s/%s" % (path_name, filename)
                return filepath
            else:
                raise Exception("No absolute path specified")
        else:
            raise Exception("Invalid file path type or undefined path type")

    def size_check(self, ami):
        """The size range test.
        Checks whether the size of the file meets a certain threshold of
        byte size. Fails if it doesn't.  Iterates action_index so that the
        next action can be done.

        Keyword Arguments:
        ami- the AMI instance used by this test, not used by this function
        but needs to be passed into sound_check_actions to continue
        """
        filesize = -1
        filesize = os.path.getsize(self.filepath)
        size = self.actions[self.action_index].get('size')
        tolerance = self.actions[self.action_index].get('tolerance')
        if ((filesize - size) > tolerance) or ((size - filesize) > tolerance):
            LOGGER.error("""File '%s' failed size check: expected %d, actual %d
                          (tolerance +/- %d""" % (
                         self.filepath, size, filesize, tolerance))
            self.test_object.set_passed(False)
            if self.auto_stop:
                self.test_object.stop_reactor()
            return
        else:
            self.action_index += 1
            self.sound_check_actions(ami)

    def energy_check(self, ami):
        """Checks the energy levels of a given sound file.
        This is done by creating a local channel into a dialplan extension
        that does a BackgroundDetect on the sound file.  The extensions must
        be defined by the user.

        Keyword Arguments:
        ami- the AMI instance used by this test
        """
        energyfile = self.filepath[:self.filepath.find('.')]
        action = self.actions[self.action_index]
        #ami.originate has no type var, so action['type'] has to be popped
        action.pop('type')
        action['variable'] = {'SOUNDFILE': energyfile}
        ami.registerEvent("UserEvent", self.verify_presence)
        dfr = ami.originate(**action)
        dfr.addErrback(self.test_object.handle_originate_failure)

    def sound_check_actions(self, ami):
        """The second, usually larger part of the sound check.
        Iterates through the actions that will be used to check various
        aspects of the given sound file.  Waits for the output of the action
        functions before continuing. If all actions have been completed resets
        the test to register for a new event as defined in the triggers. If
        all sound-file tests have been finished, sets the test to passed.

        Keyword Arguments:
        ami- the AMI instance used by this test
        """
        if self.action_index == len(self.actions):
            self.action_index = 0
            self.index += 1
            if self.index == len(self.module_config):
                LOGGER.info("Test successfully passed")
                self.test_object.set_passed(True)
                if self.auto_stop:
                    self.test_object.stop_reactor()
            else:
                self.event_register(ami)
        else:
            actiontype = self.actions[self.action_index]['type']
            if actiontype == 'size_check':
                self.size_check(ami)
            elif actiontype == 'energy_check':
                self.energy_check(ami)

    def verify_presence(self, ami, event):
        """UserEvent verifier for the energy check.
        Verifies that the userevent that was given off by the dialplan
        extension called in energy_check was a soundcheck userevent and that
        the status is pass.  Fails if the status was not pass. Iterates
        action_index if it passed so that the next action can be done.

        Keyword Arguments:
        ami- the AMI instance used by this test
        event- the event (Userevent) being picked up by the AMI that
        determines whether a correct amount of energy has been detected.
        """
        userevent = event.get("userevent")
        if not userevent:
            return
        if userevent.lower() != "soundcheck":
            return
        LOGGER.info("Checking the sound check userevent")
        ami.deregisterEvent("UserEvent", self.verify_presence)
        status = event.get("status")
        LOGGER.debug("Status of the sound check is " + status)
        if status != "pass":
            LOGGER.error("The sound check wasn't successful- test failed")
            self.test_object.set_passed(False)
            if self.auto_stop:
                self.test_object.stop_reactor()
            return
        else:
            self.action_index += 1
            self.sound_check_actions(ami)

    def sound_check_start(self, ami, event):
        """The first part of the sound_check test. Required.
        It deregisters the prerequisite event as defined in triggers so that
        it doesn't keep looking for said events. Then it checks whether the
        sound file described in the YAML exists by looking for the file with
        the given path. The filepath is determined by calling
        build_sound_file_location.  After this initial part of sound_check,
        the remaining actions are then called.

        Keyword Arguments:
        ami- the AMI instance used by this test
        event- the event (defined by the triggers section) being picked up by
        the AMI that allows the rest of the pluggable module to be accessed
        """
        config = self.module_config[self.index]
        instance_id = config.get('id', 0)
        if ami.id != instance_id:
            return

        current_trigger = config['trigger']['match']
        for key, value in current_trigger.iteritems():
            if key.lower() not in event:
                LOGGER.debug("Condition %s not in event, returning", key)
                return
            if not re.match(value, event.get(key.lower())):
                LOGGER.debug("Condition %s: %s does not match %s: %s in event",
                             key, value, key, event.get(key.lower()))
                return
            else:
                LOGGER.debug("Condition %s: %s matches %s: %s in event",
                             key, value, key, event.get(key.lower()))

        ami.deregisterEvent(current_trigger.get('event'),
                            self.sound_check_start)
        self.sound_file = config['sound-file']
        if not self.sound_file:
            raise Exception("No sound file parameters specified")
        if (not self.sound_file.get('file-name')
                or not self.sound_file.get('file-path-type')):
            raise Exception("No file or file path type specified")
        if self.sound_file.get('absolute-path'):
            file_name = self.sound_file['file-name']
            file_path_type = self.sound_file['file-path-type']
            absolute_path = self.sound_file['absolute-path']
            self.filepath = self.build_sound_file_location(file_name,
                                                           file_path_type,
                                                           absolute_path)
        else:
            file_name = self.sound_file['file-name']
            file_path_type = self.sound_file['file-path-type']
            self.filepath = self.build_sound_file_location(file_name,
                                                           file_path_type)
        #Find the filesize here if it exists
        if not os.path.exists(self.filepath):
            LOGGER.error("File '%s' does not exist!" % self.filepath)
            self.test_object.set_passed(False)
            if self.auto_stop:
                self.test_object.stop_reactor()
            return
        self.actions = self.sound_file.get('actions')
        self.sound_check_actions(ami)

    def event_register(self, ami):
        """Event register for the prerequisite event.
        Starts looking for the event defined in the triggers section of the
        YAML that allows the rest of the test to be accessed.

        Keyword Arguments:
        ami- the AMI instance used by this test
        """
        current_trigger = self.module_config[self.index]['trigger']['match']
        trigger_id = self.module_config[self.index]['trigger'].get('id', 0)
        if ami.id != trigger_id:
            return
        if not current_trigger:
            raise Exception("Missing a trigger")
        else:
            ami.registerEvent(current_trigger.get('event'),
                              self.sound_check_start)

    def ami_connect(self, ami):
        """Starts the ami_connection and then calls event_register

        Keyword Arguments:
        ami- the AMI instance used by this test
        """
        self.event_register(ami)


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


class EventActionModule(object):
    """A class that links arbitrary events with one or more actions.

    Configuration is as follows:
    config-section:
        actions:
            custom-action-name: custom.action.location
        events:
            custom-event-name: custom.event.location
        mapping:
            -
                custom-event-name:
                    event-config-goes-here
                custom-action-name:
                    action-config-goes-here

    Or if no locally-defined events or actions are desired:
    config-section:
        -
            event-name:
                event-config-goes-here
            other-event-name:
                event-config-goes-here
            action-name:
                action-config-goes-here

    Or if no locally-defined events or actions are desired and only one set is
    desired:
    config-section:
        event-name:
            event-config-goes-here
        action-name:
            action-config-goes-here

    Any event in a set will trigger all actions in a set.
    """

    def __init__(self, instance_config, test_object):
        """Constructor for pluggable modules"""
        super(EventActionModule, self).__init__()
        self.test_object = test_object
        config = instance_config
        if isinstance(config, list):
            config = {"mapping": config}
        elif isinstance(config, dict) and "mapping" not in config:
            config = {"mapping": [config]}

        # Parse out local action and event definitions
        self.local_action_registry = PluggableRegistry()
        self.local_event_registry = PluggableRegistry()

        def register_modules(config, registry):
            """Register pluggable modules into the registry"""
            for key, local_class_path in config.iteritems():
                local_class = load_and_parse_module(local_class_path)
                if not local_class:
                    raise Exception("Unable to load %s for module key %s"
                                    % (local_class_path, key))
                registry.register(key, local_class)

        if "actions" in config:
            register_modules(config["actions"], self.local_action_registry)
        if "events" in config:
            register_modules(config["events"], self.local_event_registry)

        self.event_action_sets = []
        self.parse_mapping(config)

    def parse_mapping(self, config):
        """Parse out the mapping and instantiate objects."""
        for e_a_set in config["mapping"]:
            plug_set = {"events": [], "actions": []}

            for plug_name, plug_config in e_a_set.iteritems():
                self.parse_module_config(plug_set, plug_name, plug_config)

            if 0 == len(plug_set["events"]):
                raise Exception("Pluggable set requires at least one event: %s"
                                % e_a_set)

            self.event_action_sets.append(plug_set)

    def parse_module_config(self, plug_set, plug_name, plug_config):
        """Parse module config and update the pluggable module set"""
        if self.local_event_registry.check(plug_name):
            plug_class = self.local_event_registry.get_class(plug_name)
            plug_set["events"].append(
                plug_class(self.test_object, self.event_triggered, plug_config))
        elif self.local_action_registry.check(plug_name):
            plug_class = self.local_action_registry.get_class(plug_name)
            plug_set["actions"].append(
                plug_class(self.test_object, plug_config))
        elif PLUGGABLE_EVENT_REGISTRY.check(plug_name):
            plug_class = PLUGGABLE_EVENT_REGISTRY.get_class(plug_name)
            plug_set["events"].append(
                plug_class(self.test_object, self.event_triggered, plug_config))
        elif PLUGGABLE_ACTION_REGISTRY.check(plug_name):
            plug_class = PLUGGABLE_ACTION_REGISTRY.get_class(plug_name)
            plug_set["actions"].append(
                plug_class(self.test_object, plug_config))
        else:
            raise Exception("Pluggable component '%s' not recognized"
                            % plug_name)

    def find_triggered_set(self, triggered_by):
        """Find the set that was triggered."""
        for e_a_set in self.event_action_sets:
            for event_mod in e_a_set["events"]:
                if event_mod == triggered_by:
                    return e_a_set
        return None

    def event_triggered(self, triggered_by, source=None, extra=None):
        """Run actions for the triggered set."""
        triggered_set = self.find_triggered_set(triggered_by)
        if not triggered_set:
            raise Exception("Unable to find event/action set for %s"
                            % triggered_by)

        for action_mod in triggered_set["actions"]:
            action_mod.run(triggered_by, source, extra)


class TestStartEventModule(object):
    """An event module that triggers when the test starts."""

    def __init__(self, test_object, triggered_callback, config):
        """Setup the test start observer"""
        self.test_object = test_object
        self.triggered_callback = triggered_callback
        self.config = config
        test_object.register_start_observer(self.start_observer)

    def start_observer(self, ast):
        """Notify the event-action mapper that the test has started."""
        self.triggered_callback(self, ast)
PLUGGABLE_EVENT_REGISTRY.register("test-start", TestStartEventModule)


class LogActionModule(object):
    """An action module that logs a message when triggered."""

    def __init__(self, test_object, config):
        """Setup the test start observer"""
        self.test_object = test_object
        self.message = config["message"]

    def run(self, triggered_by, source, extra):
        """Log a message."""
        LOGGER.info(self.message)
PLUGGABLE_ACTION_REGISTRY.register("logger", LogActionModule)


class CallbackActionModule(object):
    """An action module that calls the specified callback."""

    def __init__(self, test_object, config):
        """Setup the test start observer"""
        self.test_object = test_object
        self.module = config["module"]
        self.method = config["method"]

    def run(self, triggered_by, source, extra):
        """Call the callback."""
        module = __import__(self.module)
        method = getattr(module, self.method)
        self.test_object.set_passed(method(self.test_object, triggered_by,
                                           source, extra))
PLUGGABLE_ACTION_REGISTRY.register("callback", CallbackActionModule)


class StopTestActionModule(object):
    """Action module that stops a test"""

    def __init__(self, test_object, config):
        """Constructor

        Keyword Arguments:
        test_object The main test object
        config      The pluggable module config
        """
        self.test_object = test_object

    def run(self, triggered_by, source, extra):
        """Execute the action, which stops the test

        Keyword Arguments:
        triggered_by The event that triggered this action
        source       The Asterisk interface object that provided the event
        extra        Source dependent data
        """
        self.test_object.stop_reactor()
PLUGGABLE_ACTION_REGISTRY.register("stop_test", StopTestActionModule)


class PjsuaPhoneActionModule(object):
    """An action module that instructs a phone to perform an action."""

    def __init__(self, test_object, config):
        """Setup the test start observer"""
        self.test_object = test_object
        self.module = __import__("phones")
        self.method = config["action"]
        self.config = config

    def run(self, triggered_by, source, extra):
        """Instruct phone to perform action"""
        method = getattr(self.module, self.method)
        method(self.test_object, triggered_by, source, extra, self.config)
PLUGGABLE_ACTION_REGISTRY.register("pjsua_phone", PjsuaPhoneActionModule)
