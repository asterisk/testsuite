#!/usr/bin/env python
# vim: sw=3 et:
"""Module that provides classes to track a ConfBridge test.

This module has been superceded by the apptest module.

Copyright (C) 2011, Digium, Inc.
Matt Jordan <mjordan@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
"""

import sys
import logging

from test_state import TestState
from twisted.internet import reactor

sys.path.append("lib/python")

LOGGER = logging.getLogger(__name__)

class ConfbridgeChannelObject(object):
    """A tracking object that ties together information about the channels
    involved in a ConfBridge
    """

    def __init__(self, conf_bridge_channel, caller_channel, caller_ami,
                 profile_option=""):
        """Constructor

        Keyword Arguments:
        conf_bridge_channel The channel inside the Asterisk instance hosting
                            the ConfBridge
        caller_channel      The channel inside the Asterisk instance that
                            called the ConfBridge server
        caller_ami          An AMI connection back to the calling Asterisk
                            instance
        profile_option      Some string field that identifies the profile set
                            for the conf_bridge_channel
        """
        self.conf_bridge_channel = conf_bridge_channel
        self.caller_channel = caller_channel
        self.caller_ami = caller_ami
        self.profile = profile_option

class ConfbridgeTestState(TestState):
    """Base class test state for ConfBridge. Allows states to send DTMF tones,
    audio files, hangup, and otherwise interact with the conference. As this
    inherits from test_state, this is also an entry in the state engine, such
    that it will receive test event notifications. Derived classes should handle
    these state notifications, and use the methods in this class to respond
    accordingly.
    """

    def __init__(self, controller, test_case, calls=None):
        """Constructor

        Keyword Arguments:
        controller      The TestStateController managing the test
        test_case       The main test object
        calls           A dictionary (keyed by conf_bridge_channel ID) of
                        ConfbridgeChannelObjects
        """
        TestState.__init__(self, controller)
        self.test_case = test_case
        self.calls = calls or {}
        self.__previous_dtmf = {}
        self.__previous_audio = {}
        if (len(self.calls) > 0):
            for key in self.calls:
                self.__previous_dtmf[key] = ""
                self.__previous_audio[key] = ""

        LOGGER.debug(" Entering state [" + self.get_state_name() + "]")

    def register_new_caller(self, channel_object):
        """Register a new ConfbridgeChannelObject with the state engine

        Keyword Arguments:
        channel_object    An object that ties all of the various channels/AMI
                          information together
        """
        if not (channel_object.conf_bridge_channel in self.calls):
            self.calls[channel_object.conf_bridge_channel] = channel_object
            self.__previous_dtmf[channel_object.conf_bridge_channel] = ""
            self.__previous_audio[channel_object.conf_bridge_channel] = ""

    def get_state_name(self):
        """Should be overriden by derived classes and return the name of the
        current state
        """
        pass

    def handle_default_state(self, event):
        """Can be called by derived classes to output a state that is being
        ignored
        """
        msg = ("State [" + self.get_state_name() +
               "] - ignoring state change " + event['state'])
        LOGGER.debug(msg)

    def _handle_redirect_failure(self, reason):
        """Handle a redirect failure from Asterisk"""

        LOGGER.warn("Error sending redirect - test may or may not fail:")
        LOGGER.warn(reason.getTraceback())
        return reason

    def hangup(self, call_id):
        """Hangs up the current call

        Keyword Arguments:
        call_id        The channel name
        """

        if call_id in self.calls:
            chan = self.calls[call_id].caller_channel
            ami = self.calls[call_id].caller_ami
            deferred = ami.redirect(chan, "caller", "hangup", 1)
            deferred.addErrback(self._handle_redirect_failure)
        else:
            LOGGER.warn("Unknown call ID %s" % call_id)

    def send_dtmf(self, call_id, dtmf):
        """Send a DTMF signal to the server

        Keyword Arguments:
        call_id     The channel name, from the perspective of the ConfBridge app
        dtmf        The DTMF code to send
        """

        if call_id in self.calls:
            LOGGER.debug("Attempting to send DTMF %s via %s" % (dtmf, call_id))
            ami = self.calls[call_id].caller_ami
            if (self.__previous_dtmf[call_id] != dtmf):
                ami.setVar(channel=self.calls[call_id].caller_channel,
                           variable="DTMF_TO_SEND",
                           value=dtmf)
                self.__previous_dtmf[call_id] = dtmf

            # Redirect to the DTMF extension - note that we assume that we only
            # have one channel to the other asterisk instance
            deferred = ami.redirect(self.calls[call_id].caller_channel,
                                    "caller", "sendDTMF", 1)
            deferred.addErrback(self._handle_redirect_failure)
        else:
            LOGGER.warn("Unknown call ID %s" % call_id)

    def send_sound_file(self, call_id, audio_file):
        """Send a sound file to the server

        Keyword Arguments:
        call_id     The channel name, from the perspective of the ConfBridge app
        audio_file  The local path to the file to stream
        """

        if call_id in self.calls:
            LOGGER.debug("Attempting to send audio file %s via %s" %
                         (audio_file, call_id))
            ami = self.calls[call_id].caller_ami
            if (self.__previous_audio[call_id] != audio_file):
                ami.setVar(channel=self.calls[call_id].caller_channel,
                           variable="TALK_AUDIO",
                           value=audio_file)
                self.__previous_audio[call_id] = audio_file

            # Redirect to the send sound file extension - note that we assume
            # that we only have one channel to the other asterisk instance
            deferred = ami.redirect(self.calls[call_id].caller_channel,
                                    "caller", "sendAudio", 1)
            deferred.addErrback(self._handle_redirect_failure)
        else:
            LOGGER.warn("Unknown call ID %s" % call_id)

    def send_sound_file_with_dtmf(self, call_id, audio_file, dtmf):
        """Send a sound file to the server, then send a DTMF signal

        Keyword Arguments:
        call_id     The channel name, from the perspective of the ConfBridge app
        audio_file  The local path to the file to stream
        dtmf        The DTMF signal to send
    
        Note that this is necessary so that when the audio file is finished, we
        close the audio recording cleanly; otherwise, Asterisk may detect the
        end of file as a hangup
        """
        if call_id in self.calls:
            msg = ("Attempting to send audio file %s followed by %s via %s" %
                   (audio_file, dtmf, call_id))
            LOGGER.debug(msg)
            ami = self.calls[call_id].caller_ami
            if (self.__previous_audio[call_id] != audio_file):
                ami.setVar(channel=self.calls[call_id].caller_channel,
                           variable="TALK_AUDIO",
                           value=audio_file)
                self.__previous_audio[call_id] = audio_file
            if (self.__previous_dtmf[call_id] != dtmf):
                ami.setVar(channel=self.calls[call_id].caller_channel,
                           variable="DTMF_TO_SEND",
                           value=dtmf)
                self.__previous_dtmf[call_id] = dtmf

            # Redirect to the send sound file extension - note that we assume
            # that we only have one channel to the other asterisk instance

            deferred = ami.redirect(self.calls[call_id].caller_channel,
                                    "caller", "sendAudioWithDTMF", 1)
            deferred.addErrback(self._handle_redirect_failure)
        else:
            LOGGER.warn("Unknown call ID %s" % call_id)

    def schedule_dtmf(self, delay, call_id, dtmf):
        """Schedule and send a DTMF tone sometime later

        Keyword Arguments:
        delay   The number of seconds to wait
        call_id The channel name, from the perspective of the ConfBridge app
        dtmf    The DTMF code to send
        """
        reactor.callLater(delay, self.send_dtmf, call_id, dtmf)

    def schedule_sound_file(self, delay, call_id, audio_file):
        """Schedule and send an audio file

        Keyword Arguments:
        delay       The number of seconds to wait
        call_id     The channel name, from the perspective of the ConfBridge app
        audio_file  The local path to the file to stream
        """
        reactor.callLater(delay, self.send_sound_file, call_id, audio_file)
