#!/usr/bin/env python
# vim: sw=3 et:
'''
Copyright (C) 2011, Digium, Inc.
Matt Jordan <mjordan@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
'''

import sys
import os
import glob
import shutil
import logging

from TestCase import TestCase
from TestState import TestState
from TestState import TestStateController
from twisted.internet import reactor

sys.path.append("lib/python")

logger = logging.getLogger(__name__)

class ConfbridgeChannelObject:
    """
    A tracking object that ties together information about the channels
    involved in a ConfBridge
    """

    def __init__(self, conf_bridge_channel, caller_channel, caller_ami, profile_option = ""):
        """
        conf_bridge_channel    The channel inside the Asterisk instance hosting the ConfBridge
        caller_channel        The channel inside the Asterisk instance that called the ConfBridge server
        caller_ami            An AMI connection back to the calling Asterisk instance
        profile_option        Some string field that identifies the profile set for the conf_bridge_channel
        """
        self.conf_bridge_channel = conf_bridge_channel
        self.caller_channel = caller_channel
        self.caller_ami = caller_ami
        self.profile = profile_option

class ConfbridgeTestState(TestState):
    """
    Base class test state for ConfBridge.  Allows states to send DTMF tones, audio files,
    hangup, and otherwise interact with the conference.  As this inherits from TestState, this
    is also an entry in the state engine, such that it will receive test event notifications.
    Derived classes should handle these state notifications, and use the methods in this class
    to respond accordingly.
    """

    def __init__(self, controller, testCase, calls = {}):
        """
        controller      The TestStateController managing the test
        testCase        The main test object
        calls           A dictionary (keyed by conf_bridge_channel ID) of ConfbridgeChannelObjects
        """
        TestState.__init__(self, controller)
        self.testCase = testCase
        self.calls = calls
        self.__previous_dtmf = {}
        self.__previous_audio = {}
        if (len(self.calls) > 0):
            for k in self.calls:
                self.__previous_dtmf[k] = ""
                self.__previous_audio[k] = ""

        logger.debug(" Entering state [" + self.getStateName() + "]")

    def registerNewCaller(self, channel_object):
        """
        Register a new ConfbridgeChannelObject with the state engine
        channel_object    An object that ties all of the various channels / AMI information together
        """
        if not (channel_object.conf_bridge_channel in self.calls):
            self.calls[channel_object.conf_bridge_channel] = channel_object
            self.__previous_dtmf[channel_object.conf_bridge_channel] = ""
            self.__previous_audio[channel_object.conf_bridge_channel] = ""

    def getStateName(self):
        """
        Should be overriden by derived classes and return the name of the current state
        """
        pass

    def handleDefaultState(self, event):
        """
        Can be called by derived classes to output a state that is being ignored
        """
        logger.debug(" State [" + self.getStateName() + "] - ignoring state change " + event['state'])

    def __handleRedirectFailure__(self, reason):
        logger.warn("Error sending redirect - test may or may not fail:")
        logger.warn(reason.getTraceback())
        return reason

    def hangup(self, call_id):
        """
        Hangs up the current call
        call_id        The channel name
        """
        if call_id in self.calls:
            df = self.calls[call_id].caller_ami.redirect(self.calls[call_id].caller_channel, "caller", "hangup", 1)
            df.addErrback(self.__handleRedirectFailure__)
        else:
            logger.warn("Unknown call ID %s" % call_id)

    def sendDTMF(self, call_id, dtmfToSend):
        """
        Send a DTMF signal to the server
        call_id        The channel name, from the perspective of the ConfBridge app
        dtmfToSend    The DTMF code to send
        """
        if call_id in self.calls:
            logger.debug("Attempting to send DTMF %s via %s", dtmfToSend, call_id)
            if (self.__previous_dtmf[call_id] != dtmfToSend):
                self.calls[call_id].caller_ami.setVar(channel = self.calls[call_id].caller_channel, variable = "DTMF_TO_SEND", value = dtmfToSend)
                self.__previous_dtmf[call_id] = dtmfToSend
            """
            Redirect to the DTMF extension - note that we assume that we only have one channel to
            the other asterisk instance
            """
            df = self.calls[call_id].caller_ami.redirect(self.calls[call_id].caller_channel, "caller", "sendDTMF", 1)
            df.addErrback(self.__handleRedirectFailure__)
        else:
            logger.warn("Unknown call ID %s" % call_id)

    def sendSoundFile(self, call_id, audioFile):
        """
        Send a sound file to the server
        call_id        The channel name, from the perspective of the ConfBridge app
        audioFile    The local path to the file to stream
        """
        if call_id in self.calls:
            logger.debug("Attempting to send audio file %s via %s", audioFile, call_id)
            if (self.__previous_audio[call_id] != audioFile):
                self.calls[call_id].caller_ami.setVar(channel = call_id, variable = "TALK_AUDIO", value = audioFile)
                self.__previous_audio[call_id] = audioFile
            """
            Redirect to the send sound file extension - note that we assume that we only have one channel to
            the other asterisk instance
            """
            df = self.calls[call_id].caller_ami.redirect(self.calls[call_id].caller_channel, "caller", "sendAudio", 1)
            df.addErrback(self.__handleRedirectFailure__)
        else:
            logger.warn("Unknown call ID %s" % call_id)

    def sendSoundFileWithDTMF(self, call_id, audioFile, dtmfToSend):
        """
        Send a sound file to the server, then send a DTMF signal
        audioFile    The local path to the file to stream
        dtmfToSend   The DTMF signal to send
    
        Note that this is necessary so that when the audio file is finished, we close the audio recording cleanly;
        otherwise, Asterisk may detect the end of file as a hangup
        """
        if call_id in self.calls:
            logger.debug("Attempting to send audio file %s followed by %s via %s", audioFile, dtmfToSend, call_id)
            if (self.__previous_audio[call_id] != audioFile):
                self.calls[call_id].caller_ami.setVar(channel = self.calls[call_id].caller_channel, variable = "TALK_AUDIO", value = audioFile)
                self.__previous_audio[call_id] = audioFile
            if (self.__previous_dtmf[call_id] != dtmfToSend):
                self.calls[call_id].caller_ami.setVar(channel = self.calls[call_id].caller_channel, variable = "DTMF_TO_SEND", value = dtmfToSend)
                self.__previous_dtmf[call_id] = dtmfToSend
            """
            Redirect to the send sound file extension - note that we assume that we only have one channel to
            the other asterisk instance
            """
            df = self.calls[call_id].caller_ami.redirect(self.calls[call_id].caller_channel, "caller", "sendAudioWithDTMF", 1)
            df.addErrback(self.__handleRedirectFailure__)
        else:
            logger.warn("Unknown call ID %s" % call_id)

    def scheduleDTMF(self, delay, call_id, dtmfToSend):
        """
        Schedule and send a DTMF tone sometime later
        delay   The number of seconds to wait
        call_id        The channel name, from the perspective of the ConfBridge app
        dtmfToSend    The DTMF code to send
        """
        reactor.callLater(delay, self.sendDTMF, call_id, dtmfToSend)

    def scheduleSendSoundFile(self, delay, call_id, audioFile):
        """
        Schedule and send a DTMF tone sometime later
        delay   The number of seconds to wait
        call_id        The channel name, from the perspective of the ConfBridge app
        audioFile    The local path to the file to stream
        """
        reactor.callLater(delay, self.sendSoundFile, call_id, audioFile)
