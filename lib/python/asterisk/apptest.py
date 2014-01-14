"""Application test module for the pluggable module framework

This pluggable test-object and modules allows a test configuration to control
a Local channel in a long running Asterisk application. This is suitable for
testing Asterisk applications such as VoiceMail, ConfBridge, MeetMe, etc.

Copyright (C) 2012, Digium, Inc.
Matt Jordan <mjordan@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
"""

import sys
import logging
import uuid

from twisted.internet import reactor, defer

sys.path.append("lib/python")
from test_case import TestCase
from ami import AMIEventInstance

LOGGER = logging.getLogger(__name__)

class AppTest(TestCase):
    """A pluggable test object suitable for orchestrating tests against long
        running Asterisk applications"""

    _singleton_instance = None

    @staticmethod
    def get_instance(path='', test_config=None):
        """Return the singleton instance of the application test_object

        Keyword Arguments:
        path The full path to the location of the test
        test_config The test's YAML configuration object
        """
        if (AppTest._singleton_instance is None):
            # Note that the constructor sets the singleton instance.
            # This is a tad backwards, but is needed for the pluggable
            # framework.
            AppTest(path, test_config)
        return AppTest._singleton_instance

    def __init__(self, path, test_config):
        """Create the pluggable test module

        Keyword Arguments:
        path - The full path to the location of the test
        test_config - This test's configuration
        """
        super(AppTest, self).__init__(path)

        self._channel_objects = {}      # The current scenario's channels
        self._expected_results = {}     # Expected results for all scenarios
        self._event_instances = []      # The ApplicationEventInstance objects

        self.raw_test_config = test_config
        self._application = self.raw_test_config['app']
        self._scenarios = self.raw_test_config['scenarios']

        self.register_ami_observer(self._ami_connect_handler)
        self.register_stop_observer(self.end_scenario)
        self.create_asterisk()

        # Created successfully - set the singleton instance to this object
        # if we're the first instance created; otherwise, complain loudly
        if (AppTest._singleton_instance is None):
            AppTest._singleton_instance = self
        else:
            raise Exception("Singleton instance of AppTest already set!")

    def run(self):
        """Run the test.  Called when the reactor is started."""
        super(AppTest, self).run()
        self.create_ami_factory()

    def _run_scenario(self, scenario):
        """Run some scenario

        Keyword Arguments:
        scenario The scenario object to execute
        """
        LOGGER.info("Starting scenario...")

        # Create event instances not associated with a channel
        if 'events' in scenario:
            for event_config in scenario['events']:
                ae_instance = ApplicationEventInstance('', event_config, self)
                self._event_instances.append(ae_instance)

        # Create the event instances associated with a channel and the
        # corresponding channel object
        for channel_config in scenario['channels']:
            channel_id = channel_config['channel-id']
            for event_config in channel_config['events']:
                ae_instance = ApplicationEventInstance(channel_id,
                                                       event_config,
                                                       self)
                self._event_instances.append(ae_instance)

            obj = ChannelObject(ami=self.ami[0],
                                application=self._application,
                                channel_def=channel_config)
            self._channel_objects[channel_id] = obj
            LOGGER.debug("Created channel object for %s" % channel_id)

    def _ami_connect_handler(self, ami):
        """Handler for the AMI connect event

        Starts the first scenario object
        """
        self._run_scenario(self._scenarios.pop(0))
        return ami

    def _reset_scenario_objects(self):
        """Reset the scenario objects for the next iteration"""

        self._channel_objects.clear()
        self._expected_results.clear()
        for event_instance in self._event_instances:
            event_instance.dispose(self.ami[0])
        self._event_instances = []

    def _evaluate_expected_results(self):
        """Evaluate expected results for a scenario"""

        if (len(self._expected_results) == 0):
            self.set_passed(True)
            return

        for expected, result in self._expected_results.items():
            if not result:
                LOGGER.warn("Expected result %s failed!" % expected)
                self.set_passed(False)
            else:
                LOGGER.debug("Expected result %s passed" % expected)
                self.set_passed(True)

    def end_scenario(self, result=None):
        """End the current scenario"""
        self._evaluate_expected_results()
        if len(self._scenarios) == 0:
            LOGGER.info("All scenarios executed; stopping")
            self.stop_reactor()
        else:
            self._reset_scenario_objects()
            self.reset_timeout()
            self._run_scenario(self._scenarios.pop(0))
        return result

    def get_channel_object(self, channel_id):
        """Get the ChannelObject associated with a channel name

        Keywords:
        channel_id The ID of the channel to retrieve
        """
        if channel_id not in self._channel_objects:
            LOGGER.error("Unknown channel %s requested from Scenario"
                         % channel_id)
            raise Exception
        return self._channel_objects[channel_id]

    def add_expected_result(self, expected_result):
        """Add an expected result to the test_object

        Keywords:
        expected_result The name of the result that should occur
        """
        self._expected_results[expected_result] = False

    def set_expected_result(self, expected_result):
        """Set an expected result to True

        Keywords:
        expected_result The name of the result that occurred
        """
        self._expected_results[expected_result] = True


class ChannelObject(object):
    """Object that represents a channel in an application and its controlling
    mechanism.

    All tests use Local channels.  One end of the Local channel pair is sent
    into the application.  The other is dropped into a set of extensions that
    determine how the application is manipulated.  AMI redirects are used to
    manipulate the second half of the Local channel pair.
    """

    default_context = 'default'

    default_dtmf_exten = 'sendDTMF'

    default_hangup_exten = 'hangup'

    default_wait_exten = 'wait'

    default_audio_exten = 'sendAudio'

    def __init__(self, ami,
                 application,
                 channel_def):
        ''' Create a new ChannelObject

        Keywords:
        ami The AMI instance to spawn the channel in
        application The application name to test
        channel_def A dictionary of parameters to extract that will configure
            the channel object
        '''

        self._channel_id = channel_def['channel-id']
        self._channel_name = channel_def['channel-name']
        self._application = application
        self._controller_context = channel_def.get('context') or \
                                   ChannelObject.default_context
        self._controller_initial_exten = channel_def.get('exten') or \
                                         ChannelObject.default_wait_exten
        self._controller_hangup_exten = channel_def.get('hangup-exten') or \
                                        ChannelObject.default_hangup_exten
        self._controller_audio_exten = channel_def.get('audio-exten') or \
                                       ChannelObject.default_audio_exten
        self._controller_dtmf_exten = channel_def.get('dtmf-exten') or \
                                      ChannelObject.default_dtmf_exten
        self._controller_wait_exten = channel_def.get('wait-exten') or \
                                      ChannelObject.default_wait_exten
        delay = channel_def.get('delay') or 0

        self.ami = ami
        self.ami.registerEvent('Hangup', self._hangup_event_handler)
        self.ami.registerEvent('VarSet', self._varset_event_handler)
        self.ami.registerEvent('TestEvent', self._test_event_handler)
        self.ami.registerEvent('Newexten', self._new_exten_handler)
        self.ami.registerEvent('Newchannel', self._new_channel_handler)
        self._all_channels = []         # All channels we've detected
        self._candidate_channels = []   # The local pair that are ours
        self.app_channel = ''           # The local half in the application
        self.controller_channel = ''    # The local half controlling the test
        self._hungup = False
        self._previous_dtmf = ''
        self._previous_sound_file = ''
        self._test_observers = []
        self._hangup_observers = []
        self._candidate_prefix = ''
        self._unique_id = str(uuid.uuid1())
        if 'start-on-create' in channel_def and channel_def['start-on-create']:
            self.spawn_call(delay)

    def spawn_call(self, delay=0):
        """Spawn the call!

        Keyword Arguments:
        delay The amount of time to wait before spawning the call

        Returns:
        Deferred object that will be called after the call has been originated.
        The deferred will pass this object as the parameter.
        """

        def __spawn_call_callback(spawn_call_deferred):
            """Actually perform the origination"""
            self.ami.originate(channel=self._channel_name,
                    context=self._controller_context,
                    exten=self._controller_initial_exten,
                    priority='1',
                    variable={'testuniqueid': '%s' % self._unique_id})
            spawn_call_deferred.callback(self)

        spawn_call_deferred = defer.Deferred()
        reactor.callLater(delay, __spawn_call_callback,
                          spawn_call_deferred)
        return spawn_call_deferred

    def __str__(self):
        return '(Controller: %s; Application %s)' % (self.controller_channel,
                                                    self.app_channel)

    def _handle_redirect_failure(self, reason):
        """If a redirect fails, complain loudly"""
        LOGGER.warn("Error occurred while sending redirect:")
        LOGGER.warn(reason.getTraceback())
        return reason

    def _send_redirect(self, extension):
        """Redirect the controlling channel into some extension"""
        if self._hungup:
            LOGGER.debug("Ignoring redirect to %s; channel %s is hungup" %
                         (extension, self.controller_channel))
            return
        deferred = self.ami.redirect(self.controller_channel,
                                     self._controller_context,
                                     extension,
                                     1)
        deferred.addErrback(self._handle_redirect_failure)

    def hangup(self, delay=0):
        """Hang up the channel

        Keywords:
        delay How long to wait before hanging up the channel

        Returns:
        A deferred object called when the hangup is initiated
        """
        def __hangup_callback(hangup_deferred):
            """Deferred callback when a hangup has started"""
            self._send_redirect(self._controller_hangup_exten)
            hangup_deferred.callback(self)

        hangup_deferred = defer.Deferred()
        reactor.callLater(delay, __hangup_callback, hangup_deferred)
        return hangup_deferred

    def is_hungup(self):
        """Return whether or not the channels owned by this object are hungup"""
        return self._hungup

    def register_test_observer(self, callback):
        """Register an observer to be called when a test event is fired that
        affects this channel

        The callback called will be passed two parameters:
        1) This object
        2) The test event that caused the callback to be called
        """
        self._test_observers.append(callback)

    def register_hangup_observer(self, callback):
        """Register an observer to be called when a hangup is detected

        The callback called will be passed two parameters:
        1) This object
        2) The hangup event that caused the callback to be called
        """
        self._hangup_observers.append(callback)

    def send_dtmf(self, dtmf, delay=0):
        """Send DTMF into the conference

        Keywords:
        dtmf The DTMF string to send
        delay Schedule the sending of the DTMF for some time period

        Returns:
        A deferred object that will be called when the DTMF starts to be sent.
        The callback parameter will be this object.
        """

        def __send_dtmf_initial(param):
            """Initial callback called by the reactor. This sets the dialplan
            variable DTMF_TO_SEND to the dtmf value to stream"""
            dtmf, dtmf_deferred = param
            if (self._previous_dtmf != dtmf):
                deferred = self.ami.setVar(channel=self.controller_channel,
                                 variable='DTMF_TO_SEND',
                                 value=dtmf)
                deferred.addCallback(__send_dtmf_redirect, dtmf_deferred)
                self._previous_dtmf = dtmf
            else:
                __send_dtmf_redirect(None, dtmf_deferred)

        def __send_dtmf_redirect(result, deferred):
            """Second callback called when the dialplan variable has been
            set. This redirect the controlling channel to the sendDTMF
            extension"""
            self._send_redirect(self._controller_dtmf_exten)
            deferred.callback(self)
            return deferred

        LOGGER.debug("Sending DTMF %s over Controlling Channel %s" %
                     (dtmf, self.controller_channel))
        dtmf_deferred = defer.Deferred()
        reactor.callLater(delay, __send_dtmf_initial, (dtmf, dtmf_deferred))
        return dtmf_deferred

    def stream_audio(self, sound_file, delay=0):
        """Stream an audio sound file into the conference

        Keywords:
        sound_file The path of the sound file to stream
        delay Schedule the sending of the audio for some time period

        Returns:
        A deferred object that will be called when the aduio starts to be sent.
        The callback parameter will be this object.
        """

        def __stream_audio_initial(param):
            """Initial callback called by the reactor. This sets the dialplan
            variable TALK_AUDIO to the file to stream"""
            sound_file, audio_deferred = param
            if (self._previous_sound_file != sound_file):
                deferred = self.ami.setVar(channel=self.controller_channel,
                                variable="TALK_AUDIO",
                                value=sound_file)
                deferred.addCallback(__stream_audio_redirect, audio_deferred)
                self._previous_sound_file = sound_file
            else:
                __stream_audio_redirect(None, audio_deferred)

        def __stream_audio_redirect(result, deferred):
            """Second callback called when the dialplan variable has been
            set.  This redirect the controlling channel to the sendAudio
            extension"""
            self._send_redirect(self._controller_audio_exten)
            deferred.callback(self)
            return deferred

        LOGGER.debug("Streaming Audio File %s over Controlling Channel %s" %
                     (sound_file, self.controller_channel))
        audio_deferred = defer.Deferred()
        reactor.callLater(delay, __stream_audio_initial,
                          (sound_file, audio_deferred))
        return audio_deferred

    def stream_audio_with_dtmf(self,
                               sound_file,
                               dtmf,
                               sound_delay=0,
                               dtmf_delay=0):
        """Stream an audio sound file into the conference followed by some DTMF

        Keywords:
        sound_file The path of the sound file to stream
        dtmf The DTMF to send
        sound_delay Schedule the sending of the audio for some time period
        dtmf_delay Schedule the sending of the DTMF for some time period

        Returns:
        A deferred object that will be called when both the audio and dtmf
        have been triggered
        """

        def __start_dtmf(param):
            """Triggered when the audio has started"""
            dtmf, dtmf_delay, audio_dtmf_deferred = param
            start_deferred = self.send_dtmf(dtmf, dtmf_delay)
            start_deferred.addCallback(__dtmf_sent, audio_dtmf_deferred)
            return param

        def __dtmf_sent(result, deferred):
            """Triggered when the DTMF has started"""
            deferred.callback(self)
            return deferred

        audio_dtmf_deferred = defer.Deferred()
        param_tuple = (dtmf, dtmf_delay, audio_dtmf_deferred)
        deferred = self.stream_audio(sound_file, sound_delay)
        deferred.addCallback(__start_dtmf, param_tuple)
        return audio_dtmf_deferred

    def _evaluate_candidates(self):
        """Determine if we know who our candidate channel is"""
        if len(self._candidate_prefix) == 0:
            return
        for channel in self._all_channels:
            if self._candidate_prefix in channel:
                LOGGER.debug("Adding candidate channel %s" % channel)
                self._candidate_channels.append(channel)

    def _new_channel_handler(self, ami, event):
        """Handler for the Newchannel event"""
        if event['channel'] not in self._all_channels:
            self._all_channels.append(event['channel'])
            self._evaluate_candidates()
        return (ami, event)

    def _hangup_event_handler(self, ami, event):
        """Handler for the Hangup event"""
        if self._hungup:
            # Don't process multiple hangup events
            return
        if 'channel' not in event:
            return
        if self.controller_channel == event['channel']:
            LOGGER.debug("Controlling Channel %s hangup event detected" %
                         self.controller_channel)
        elif self.app_channel == event['channel']:
            LOGGER.debug("Application Channel %s hangup event detected" %
                         self.app_channel)
        else:
            # Not us!
            return

        for observer in self._hangup_observers:
            observer(self, event)
        self._hungup = True
        return (ami, event)

    def _varset_event_handler(self, ami, event):
        """Handler for the VarSet event

        Note that we only care about the testuniqueid channel variable, which
        will tell us which channels we're responsible for
        """
        if (event['variable'] != 'testuniqueid'):
            return
        if (event['value'] != self._unique_id):
            return
        channel_name = event['channel'][:len(event['channel'])-2]
        LOGGER.debug("Detected channel %s" % channel_name)
        self._candidate_prefix = channel_name
        self._evaluate_candidates()
        return (ami, event)

    def _test_event_handler(self, ami, event):
        """Handler for test events"""
        if 'channel' not in event:
            return
        if self.app_channel not in event['channel'] and \
            self.controller_channel not in event['channel']:
            return
        for observer in self._test_observers:
            observer(self, event)
        return (ami, event)

    def _new_exten_handler(self, ami, event):
        """Handler for new extensions. This figures out which half of a
        local channel dropped into the specified app"""

        if 'channel' not in event or 'application' not in event:
            return
        if event['application'] != self._application:
            return
        if event['channel'] not in self._candidate_channels:
            # Whatever channel just entered isn't one of our channels.  This
            # could occur if multiple channels are entering a Conference in a
            # test.
            return

        self.app_channel = event['channel']
        self._candidate_channels.remove(event['channel'])
        self.controller_channel = self._candidate_channels[0]
        LOGGER.debug("Setting App Channel to %s; Controlling Channel to %s"
                     % (self.app_channel, self.controller_channel))
        return (ami, event)


class ApplicationEventInstance(AMIEventInstance):
    """An object that responds to AMI events that occur while a channel is in
    an application and initiates a sequence of actions on a channel object as a
    result

    Note that this is a pluggable object, but is created automatically by
    the configuration of the AppTest test object.
    """

    def __init__(self, channel_id, instance_config, test_object):
        """Constructor

        Keyword Arguments:
        channel_id The unique ID of the channel pair
        instance_config The configuration object for this pluggable object
        test_object The test object this pluggable instance attaches to
        """
        super(ApplicationEventInstance, self).__init__(instance_config,
                                                       test_object)
        self.channel_id = channel_id
        self.actions = []

        # create actions from the definitions
        for action_def in instance_config['actions']:
            self.actions.append(
                ActionFactory.create_action(action_def))
        self.__current_action = 0
        self.channel_obj = None
        self.test_object = test_object

        # Force registration, as this object may be used in a scenario that
        # is executed long after AMI connection
        self.register_handler(self.test_object.ami[0])

    def event_callback(self, ami, event):
        """Override of AMIEventInstance event_callback."""

        # If we aren't matching on a channel, then just execute the actions
        if 'channel' not in event or len(self.channel_id) == 0:
            self.execute_next_action()
            return

        self.channel_obj = self.test_object.get_channel_object(self.channel_id)
        # Its possible that the event matching could only be so accurate, as
        # there may be multiple Local channel in the same extension.  Make
        # sure that this is actually for us by checking the Asterisk channel
        # names
        if (self.channel_obj.app_channel in event['channel']
            or self.channel_obj.controller_channel in event['channel']):
            self.execute_next_action()

    def execute_next_action(self, result=None):
        """Execute the next action in the sequence"""

        if (len(self.actions) == 0):
            return

        LOGGER.debug("Executing action %d on %s" %
                     (self.__current_action, str(self.channel_obj)))
        ret_obj = self.actions.pop(0)(self.channel_obj)

        self.__current_action += 1
        if ret_obj is not None:
            ret_obj.addCallback(self.execute_next_action)
        else:
            reactor.callLater(0, self.execute_next_action)
        return result

    def dispose(self, ami):
        """Have this object remove itself from the AMI connection"""
        super(ApplicationEventInstance, self).dispose(ami)
        # Clear the actions just to ensure they can't be executed again
        self.actions = []


class ActionStartCall(object):
    """Functor that spawns a call"""

    def __init__(self, action_config):
        """Constructor

        Keyword Arguments:
        action_config The config dictionary for this functor
        """
        self.test_object = AppTest.get_instance()
        self.channel_id = action_config['channel-id']
        self.delay = 0 if 'delay' not in action_config \
            else action_config['delay']

    def __call__(self, channel_object):
        spawn_channel = self.test_object.get_channel_object(self.channel_id)
        return spawn_channel.spawn_call(delay=self.delay)


class ActionSendDtmf(object):
    """Functor that sends DTMF to a channel"""

    def __init__(self, action_config):
        """Constructor

        Keyword Arguments:
        action_config The config dictionary for this functor
        """
        self.dtmf = action_config['dtmf']
        self.delay = 0 if 'delay' not in action_config \
            else int(action_config['delay'])
        if 'channel-id' in action_config:
            self.channel_id = action_config['channel-id']
        else:
            self.channel_id = ''

    def __call__(self, channel_object):
        channel = channel_object
        if (len(self.channel_id) > 0):
            test_object = AppTest.get_instance()
            channel = test_object.get_channel_object(self.channel_id)
        LOGGER.debug("Sending DTMF %s over Controlling Channel %s" %
                     (self.dtmf, channel))
        return channel.send_dtmf(dtmf=self.dtmf,
                                 delay=self.delay)


class ActionStreamAudio(object):
    """Functor that streams audio to a channel"""

    def __init__(self, action_config):
        """Constructor

        Keyword Arguments:
        action_config The config dictionary for this functor
        """
        self.sound_file = action_config['sound-file']
        self.delay = 0 if 'delay' not in action_config \
            else int(action_config['delay'])

    def __call__(self, channel_object):
        return channel_object.stream_audio(sound_file=self.sound_file,
                                           delay=self.delay)


class ActionStreamAudioWithDtmf(object):
    """Functor that streams audio followed by dtmf to a channel"""

    def __init__(self, action_config):
        """Constructor

        Keyword Arguments:
        action_config The config dictionary for this functor
        """
        self.sound_file = action_config['sound-file']
        self.dtmf = action_config['dtmf']
        self.dtmf_delay = 0 if 'dtmf-delay' not in action_config \
            else int(action_config['dtmf-delay'])
        self.sound_delay = 0 if 'sound-delay' not in action_config \
            else int(action_config['sound-delay'])

    def __call__(self, channel_object):
        return channel_object.stream_audio_with_dtmf(sound_file=self.sound_file,
                                                dtmf=self.dtmf,
                                                sound_delay=self.sound_delay,
                                                dtmf_delay=self.dtmf_delay)


class ActionSetExpectedResult(object):
    """Functor that sets some expected result on the channel object"""

    def __init__(self, action_config):
        """Constructor

        Keyword Arguments:
        action_config The config dictionary for this functor
        """
        self.expected_result = action_config['expected-result']
        self.test_object = AppTest.get_instance()
        self.test_object.add_expected_result(self.expected_result)

    def __call__(self, channel_object):
        def __raise_deferred(param):
            """Raise the deferred callback notifying everyone of the result"""
            deferred, channel_object = param
            deferred.callback(channel_object)
            return param

        LOGGER.info("Expected Result: %s" % self.expected_result)
        self.test_object.set_expected_result(self.expected_result)
        deferred_result = defer.Deferred()
        param = (deferred_result, channel_object)
        reactor.callLater(0, __raise_deferred, param)
        return deferred_result


class ActionHangup(object):
    """Functor that hangs the channel up"""

    def __init__(self, action_config):
        self.delay = 0 if 'delay' not in action_config \
            else int(action_config['delay'])
        if 'channel-id' in action_config:
            self.channel_id = action_config['channel-id']
        else:
            self.channel_id = ''

    def __call__(self, channel_object):
        hangup_channel = channel_object
        if (len(self.channel_id) > 0):
            test_object = AppTest.get_instance()
            hangup_channel = test_object.get_channel_object(self.channel_id)
        LOGGER.info("Hanging up channel object %s" % str(hangup_channel))
        return hangup_channel.hangup(self.delay)


class ActionFailTest(object):
    """Functor that auto-fails the test"""

    def __init__(self, action_config):
        self.message = "Auto failing test!" if 'message' not in action_config \
            else action_config['message']

    def __call__(self, channel_object):
        test_object = AppTest.get_instance()
        LOGGER.error(self.message)
        test_object.set_passed(False)
        return None


class ActionEndScenario(object):
    """Functor that signals to the AppTest object that the scenario has ended"""

    def __init__(self, action_config):
        self.message = "Ending scenario..." if 'message' not in action_config \
            else action_config['message']

    def __call__(self, channel_object):
        test_object = AppTest.get_instance()
        LOGGER.info(self.message)
        test_object.end_scenario()
        return None


class ActionSendMessage(object):
    """Functor that sends some AMI message"""

    def __init__(self, action_config):
        self.add_app_channel = False if 'add-app-channel' not in action_config \
            else action_config['add-app-channel']
        self.add_control_channel = False if 'add-control-channel' not in action_config \
            else action_config['add-control-channel']
        if (self.add_app_channel and self.add_control_channel):
            raise Exception('Only one channel can be added to the message!')
        self.message_fields = action_config['fields']

    def __call__(self, channel_object):
        if self.add_app_channel:
            self.message_fields['Channel'] = channel_object.app_channel
        elif self.add_control_channel:
            self.message_fields['Channel'] = channel_object.controller_channel
        LOGGER.debug("Sending message: %s" % str(self.message_fields))
        channel_object.ami.sendMessage(self.message_fields)


class ActionFactory(object):
    """A static class factory that maps action objects to text descriptions of
    those objects, and provides a factory method for creating them"""

    __action_definitions = {'start-call': ActionStartCall,
                            'send-dtmf': ActionSendDtmf,
                            'stream-audio': ActionStreamAudio,
                            'stream-audio-with-dtmf': ActionStreamAudioWithDtmf,
                            'set-expected-result': ActionSetExpectedResult,
                            'hangup': ActionHangup,
                            'fail-test': ActionFailTest,
                            'end-scenario': ActionEndScenario,
                            'send-ami-message': ActionSendMessage,}

    @staticmethod
    def create_action(action_def):
        """Create the specified action

        Returns:
        An action functor that must be called with the channel to invoke the
        action on
        """

        action_type = action_def['action-type']
        if action_type not in ActionFactory.__action_definitions:
            raise ValueError('Unknown Action Type %s' % action_type)
        return ActionFactory.__action_definitions[action_type](action_def)
