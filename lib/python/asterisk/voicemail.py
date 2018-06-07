#!/usr/bin/env python
# vim: sw=3 et:
"""Module used for testing app_voicemail

Note that this module has been superceded by the pluggable
framework and the apptest module.

Copyright (C) 2011, Digium, Inc.
Matt Jordan <mjordan@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
"""

import sys
import os
import glob
import shutil
import logging
import time
import random

from config import ConfigFile
from test_case import TestCase
from test_state import TestState, TestStateController, FailureTestState

sys.path.append("lib/python")

LOGGER = logging.getLogger(__name__)


class TestCondition(object):
    """Class that holds the state of some test condition.

    This class holds the state of a test condition and allows a callback
    function to be used to evaluate whether or not that test condition has
    passed
    """

    def __init__(self, evaluate_fn=None, test_condition_data=None):
        """Constructor

        Keyword Arguments:
        evaluate_fn         Function used to evaluate the condition. This
                            fuction should return True or False, and take in
                            two parameters:
                                - a value to be evaluated
                                - the test_condition_data passed to this
                                  constructor
        test_condition_data Some piece of data that will be passed to the
                            evaluate_fn
        """

        self._evaluate_fn = evaluate_fn
        self.test_condition_data = test_condition_data
        self.current_state = False

    def evaluate(self, value):
        """Evaluate the test condition

        Keyword Arguments:
        value    The value to evaluate
        """
        if self._evaluate_fn is not None:
            self.current_state = self._evaluate_fn(value, self)
        else:
            LOGGER.warn("No evaluate function defined, setting "
                        "current_state to [%s]" % str(value))
            self.current_state = value
        return


def handle_redirect_failure(reason):
    """Generic AMI redirect failure handler"""

    LOGGER.warn("Error sending redirect - test may or may not fail:")
    LOGGER.warn(reason.getTraceback())
    return reason


class VoiceMailTest(TestCase):
    """Base class for voice mail tests that use TestStateController"""

    # The formats a message can be left in
    formats = ["ulaw", "wav", "WAV"]

    # The default expected channel to be used to send info to the voicemail
    # server
    default_sender_channel = "PJSIP/ast1-00000000"

    def __init__(self):
        """Constructor"""
        super(VoiceMailTest, self).__init__()

        self.ami_receiver = None
        self.ami_sender = None
        self.ast_sender = None
        self._test_conditions = {}
        self._previous_audio = ""
        self._previous_dtmf = ""
        self.sender_channel = VoiceMailTest.default_sender_channel
        self.test_state_controller = None

    def create_test_controller(self):
        """Create the test controller.

        This should be called once ami_receiver and ami_sender have both been
        set by the test derived from this class.
        """
        if (self.ami_receiver is not None and self.ami_sender is not None):
            self.test_state_controller = TestStateController(self,
                                                             self.ami_receiver)

    def hangup(self):
        """Hang up the current call"""

        if self.ast_sender is None:
            msg = "Attempting to send hangup to non-existant Asterisk instance"
            LOGGER.error(msg)
            failure = FailureTestState(self.condition_controller)
            self.test_state_controller.change_state(failure)
            return

        deferred = self.ami_sender.redirect(self.sender_channel,
                                            "voicemailCaller",
                                            "hangup",
                                            1)
        deferred.addErrback(handle_redirect_failure)

    def send_dtmf(self, dtmf_to_send):
        """Send a DTMF signal to the voicemail server

        Keyword Arguments:
        dtmf_to_send    The DTMF code to send
        """
        LOGGER.info("Attempting to send DTMF " + dtmf_to_send)
        if self.ami_sender is None:
            LOGGER.error("Attempting to send DTMF to non-connected caller AMI")
            failure = FailureTestState(self.condition_controller)
            self.test_state_controller.change_state(failure)
            return

        if (self._previous_dtmf != dtmf_to_send):
            self.ami_sender.setVar(channel="", variable="DTMF_TO_SEND",
                                   value=dtmf_to_send)
            self._previous_dtmf = dtmf_to_send

        # Redirect to the DTMF extension - note that we assume that we only have
        # one channel to the other asterisk instance
        deferred = self.ami_sender.redirect(self.sender_channel,
                                            "voicemailCaller",
                                            "sendDTMF",
                                            1)
        deferred.addErrback(handle_redirect_failure)

    def send_sound_file(self, audio_file):
        """Send a sound file to the voicemail server

        Keyword Arguments:
        audio_file    The local path to the file to stream
        """

        if self.ami_sender is None:
            msg = "Attempting to send sound file to non-connected caller AMI"
            LOGGER.error(msg)
            failure = FailureTestState(self.condition_controller)
            self.test_state_controller.change_state(failure)
            return

        if (self._previous_audio != audio_file):
            self.ami_sender.setVar(channel="", variable="TALK_AUDIO",
                                   value=audio_file)
            self._previous_audio = audio_file

        # Redirect to the send sound file extension - note that we assume that
        # we only have one channel to the other asterisk instance
        deferred = self.ami_sender.redirect(self.sender_channel,
                                            "voicemailCaller",
                                            "sendAudio",
                                            1)
        deferred.addErrback(handle_redirect_failure)

    def send_sound_file_with_dtmf(self, audio_file, dtmf_to_send):
        """Send a sound file to the voicemail server, then send a DTMF signal

        Keyword Arguments:
        audio_file    The local path to the file to stream
        dtmf_to_send   The DTMF signal to send

        Note that this is necessary so that when the audio file is finished, we
        close the audio recording cleanly; otherwise, Asterisk will detect the
        end of file as a hangup
        """
        if self.ami_sender is None:
            msg = "Attempting to send sound/DTMF to non-connected caller AMI"
            LOGGER.error(msg)
            failure = FailureTestState(self.condition_controller)
            self.test_state_controller.change_state(failure)
            return

        if (self._previous_audio != audio_file):
            self.ami_sender.setVar(channel="", variable="TALK_AUDIO",
                                   value=audio_file)
            self._previous_audio = audio_file
        if (self._previous_dtmf != dtmf_to_send):
            self.ami_sender.setVar(channel="", variable="DTMF_TO_SEND",
                                   value=dtmf_to_send)
            self._previous_dtmf = dtmf_to_send

        # Redirect to the appropriate extension - note that we assume that
        # we only have one channel to the other asterisk instance
        deferred = self.ami_sender.redirect(self.sender_channel,
                                            "voicemailCaller",
                                            "sendAudioWithDTMF",
                                            1)
        deferred.addErrback(handle_redirect_failure)

    def add_test_condition(self, condition_name, condition):
        """Add a new test condition to track

        Keyword Arguments:
        condition_name   The unique name of the condition
        condition        The TestCondition object
        """
        self._test_conditions[condition_name] = condition

    def set_test_condition(self, condition_name, value):
        """Set a test condition to the specified value, and evalute whether or
        not it has passed

        Keyword Arguments:
        condition_name   The unique name of the condition
        value            The value to pass to the evaluation checker
        """
        if condition_name in self._test_conditions.keys():
            self._test_conditions[condition_name].evaluate(value)

    def get_test_condition(self, condition_name):
        """Get the current state of a test condition

        Keyword Arguments:
        condition_name    The unique name of the condition

        Returns:
        True if the condition has passed; False otherwise
        """
        if condition_name in self._test_conditions.keys():
            return self._test_conditions[condition_name].current_state
        return False

    def check_test_conditions(self):
        """Check all test conditions

        Returns:
        True if all have passed; False if any have not
        """
        ret_val = True
        for key, value in self._test_conditions.items():
            if not value.current_state:
                LOGGER.warn("Test Condition [" + key + "] has not passed")
                ret_val = False
        return ret_val


class VoiceMailState(TestState):
    """Base class for VoiceMail TestEvent state machine handling

    This class exists mostly to share the VoiceMailTest object across the
    concrete class implementations
    """

    def __init__(self, controller, voice_mail_test):
        """Constructor

        Keyword Arguments:
        controller        The TestStateController managing the test
        voice_mail_test   The main test object
        """
        super(VoiceMailState, self).__init__(controller)
        self.voice_mail_test = voice_mail_test
        if self.voice_mail_test is None:
            msg = "Failed to set voicemail test object"
            LOGGER.error(msg)
            raise RuntimeError(msg)
        LOGGER.debug("Entering state [" + self.get_state_name() + "]")

    def get_state_name(self):
        """The name of this state

        Returns:
        The name of the current state
        """
        pass

    def handle_default_state(self, event):
        """Can be called by derived classes to output an ignored state"""
        LOGGER.debug("State [" + self.get_state_name() +
                     "] - ignoring state change " + event['state'])


class VoiceMailMailboxManagement(object):
    """Class that manages creation of, verification of, and teardown of Asterisk
    mailboxes on the local filesystem
    """

    # The parent directory that this test resides in
    test_parent_dir = "tests/apps/voicemail"

    # Name of the folder for new messages
    inbox_folder_name = "INBOX"

    # Name of the folder for temporary messages
    temp_folder_name = "tmp"

    # Name of the folder for old messages
    old_folder_name = "Old"

    # Name of the folder for urgent messages
    urgent_folder_name = "Urgent"

    # Name of the folder for recorded greetings
    greetings_folder_name = "greet"

    def __init__(self, ast):
        """Constructor

        Keyword Arguments:
        ast    The instance of Asterisk to track
        """
        self.__ast = ast
        self.voicemail_directory = (self.__ast.directories['astspooldir'] +
                                    '/voicemail')
        self.created_voicemails = {}

    def create_mailbox(self, context, mailbox, create_all_folders=False):
        """Create the basic folders needed for a mailbox on the file system

        Keyword Arguments:
        context             The context that the mailbox will exist under
        mailbox             The mailbox to create
        create_all_folders  Optional parameter that will create all of the
                            various folders.

        In general, app_voicemail should be responsible for making the folders
        on the file system as needed. This method should only be needed when we
        want to bypass some of the standard applications and create a known
        state of a voicemail mailbox

        Returns:
        True on success, False on error
        """

        mailbox_path = (self.__ast.base +
                        "%(vd)s/%(c)s/%(m)s" % {'vd': self.voicemail_directory,
                                                'c': context, 'm': mailbox})

        try:
            if not os.path.isdir(mailbox_path):
                os.makedirs(mailbox_path)

            if not create_all_folders:
                return True

            inbox_path = ("%(mp)s/%(f)s" % {
                'mp': mailbox_path,
                'f': VoiceMailMailboxManagement.inbox_folder_name})
            if not os.path.isdir(inbox_path):
                os.makedirs(inbox_path)

            temp_path = ("%(mp)s/%(f)s" % {
                'mp': mailbox_path,
                'f': VoiceMailMailboxManagement.temp_folder_name})
            if not os.path.isdir(temp_path):
                os.makedirs(temp_path)

            old_path = ("%(mp)s/%(f)s" % {
                'mp': mailbox_path,
                'f': VoiceMailMailboxManagement.old_folder_name})
            if not os.path.isdir(old_path):
                os.makedirs(old_path)

            urgent_path = ("%(mp)s/%(f)s" % {
                'mp': mailbox_path,
                'f': VoiceMailMailboxManagement.urgent_folder_name})
            if not os.path.isdir(urgent_path):
                os.makedirs(urgent_path)

            greetings_path = ("%(mp)s/%(f)s" % {
                'mp': mailbox_path,
                'f': VoiceMailMailboxManagement.greetings_folder_name})
            if not os.path.isdir(greetings_path):
                os.makedirs(greetings_path)

        except IOError as io_error:
            if io_error.errno == errno.EACCESS:
                LOGGER.error("You do not have sufficient permissions to "
                             "perform the necessary directory manipulations")
                return False

        return True

    def create_dummy_voicemail(self, context, mailbox, folder, msgnum, formats):
        """Creates a dummy voicemail in the specified mailbox / folder

        Keyword Arguments:
        context    The context of the mailbox
        mailbox    The mailbox
        folder     The folder to create the voicemail in
        msgnum     The message number
        formats    The formats to create the sound file as

        The 'formats' merely append particular designators on the end of the
        sound file, /voicemail/sounds/talking.  The actual sound file is not
        converted.

        Returns:
        True if the voicemail was created successfully
        False otherwise
        """

        if not self.check_folder_exists(context, mailbox, folder):
            return False

        msg_name = 'msg%04d' % (msgnum)
        msg_env_name = msg_name + ".txt"
        msg_env_path = (self.__ast.base +
                        "%(vd)s/%(c)s/%(m)s/%(f)s/%(n)s" % {
                            'vd': self.voicemail_directory,
                            'c': context, 'm': mailbox, 'f': folder, 'n': msg_env_name})

        random.seed()
        msg_id = (str(int(time.time())) + "-" +
                  str(random.randrange(0, 1, sys.maxint - 1)))

        with open(msg_env_path, 'w') as envelope_file:
            envelope_file.write(';\n')
            envelope_file.write('; Message Information file\n')
            envelope_file.write(';\n')
            envelope_file.write('[message]\n')
            envelope_file.write('origmailbox=' + mailbox + '\n')
            envelope_file.write('context=' + context + '\n')
            envelope_file.write('macrocontext=\n')
            envelope_file.write('exten=' + mailbox + '\n')
            envelope_file.write('rdnis=unknown\n')
            envelope_file.write('priority=2\n')
            envelope_file.write('callerchan=SIP/ast1-00000000\n')
            envelope_file.write('callerid=\"Anonymous\"<555-5555>\n')
            envelope_file.write('origdate=Tue Aug  9 10:05:13 PM UTC 2011\n')
            envelope_file.write('origtime=1312927513\n')
            envelope_file.write('msg_id=%s\n' % msg_id)
            if (folder == VoiceMailMailboxManagement.urgent_folder_name):
                envelope_file.write('flag=Urgent\n')
            else:
                envelope_file.write('flag=\n')
            envelope_file.write('category=tt-weasels\n')
            envelope_file.write('duration=6\n')

        for snd_format in formats:
            msg_format_name = msg_name + '.' + snd_format
            msg_format_path = (self.__ast.base +
                               "%(vd)s/%(c)s/%(m)s/%(f)s/%(n)s" % {
                                   'vd': self.voicemail_directory,
                                   'c': context,
                                   'm': mailbox,
                                   'f': folder,
                                   'n': msg_format_name})
            audio_file = os.path.join(os.getcwd(),
                                      "%s/sounds/talking.ulaw" %
                                      (self.test_parent_dir))
            shutil.copy(audio_file, msg_format_path)

        if folder not in self.created_voicemails.keys():
            self.created_voicemails[folder] = []
        self.created_voicemails[folder].append((msgnum, msg_id))
        return True

    def check_folder_exists(self, context, mailbox,
                            folder=inbox_folder_name):
        """Checks that a folder exists for a particular user

        Keyword Arguments:
        context    The context of the mailbox
        mailbox    The mailbox
        folder     The folder to check; defaults to the default inbox name

        Returns:
        True if the folder exists
        False otherwise
        """

        mailbox_path = (self.__ast.base + "%(vd)s/%(c)s/%(m)s" %
                        {'vd': self.voicemail_directory,
                         'c': context,
                         'm': mailbox})

        if not (os.path.exists(mailbox_path)):
            return False

        folder_path = "%(mp)s/%(f)s" % {'mp': mailbox_path, 'f': folder}
        return os.path.exists(folder_path)

    def check_voicemail_exists(self, context, mailbox, msgnum, list_formats,
                               folder=inbox_folder_name):
        """Check if a voicemail exists on the filesystem

        Keyword Arguments:
        context         The context of the mailbox
        mailbox         The mailbox
        msgnum          The 1-based index of the voicemail to check for
        list_formats    The formats we expect to be recorded for us
        folder          The folder to check under; default to the default
                        inbox name

        Returns:
        True if the voicemail exists
        False otherwise
        """

        ret_val = True
        msg_name = 'msg%04d' % (msgnum)

        for snd_format in list_formats:
            file_name = msg_name + "." + snd_format
            ret_val = ret_val & self.check_voice_file_exists(context,
                                                             mailbox,
                                                             file_name,
                                                             folder)

        # make sure we have the message envelope file
        file_name = msg_name + ".txt"
        ret_val = ret_val & self.check_voice_file_exists(context,
                                                         mailbox,
                                                         file_name,
                                                         folder)
        return ret_val

    def check_greeting_exists(self, context, mailbox, msg_name, list_formats):
        """Check if a voicemail greeting exists on the filesystem

        Keyword Arguments:
        context      The context of the mailbox
        mailbox      The mailbox
        msg_name     The name of the greeting to find
        list_formats The formats we expect to be recorded for us

        Returns:
        True if the greeting exists
        False otherwise
        """
        ret_val = True

        for snd_format in list_formats:
            file_name = msg_name + "." + snd_format
            ret_val = ret_val & self.check_voice_file_exists(context,
                                                             mailbox,
                                                             file_name,
                                                             "")
        return ret_val

    def check_voicemail_property(self, context, mailbox, msgnum,
                                 property_name, property_value,
                                 folder=inbox_folder_name):
        """Check if a voicemail has the property specified

        Keyword Arguments:
        context         The context of the mailbox
        mailbox         The mailbox
        msgnum          The 1-based index of the voicemail to check for
        property_name   The name of the property to check
        property_value  The value to check for
        folder          The folder to check under; default to the default inbox
                        name

        Returns:
        True if the voicemail has the property and value specified
        False otherwise
        """
        list_formats = []
        if not self.check_voicemail_exists(context, mailbox, msgnum,
                                           list_formats, folder):
            return False

        msg_name = 'msg%(msgnum)04d' % {"msgnum": msgnum}
        msg_name = msg_name + ".txt"
        msg_path = (self.__ast.base + "%(vd)s/%(c)s/%(m)s/%(f)s/%(n)s" % {
                    'vd': self.voicemail_directory,
                    'c': context,
                    'm': mailbox,
                    'f': folder,
                    'n': msg_name})

        config_file = ConfigFile(msg_path)
        for cat in config_file.categories:
            if cat.name == 'message':
                for kvp in cat.options:
                    if kvp[0] == property_name and kvp[1] == property_value:
                        return True
        return False

    class UserObject(object):
        """An object that holds voicemail user information"""

        def __init__(self):
            """Constructor"""
            self.password = ""
            self.fullname = ""
            self.emailaddress = ""
            self.pageraddress = ""

    def get_user_object(self, context, mailbox, source_file="voicemail.conf"):
        """Gets user information from the voicemail configuration file

        Keyword Arguments:
        context     The context of the mailbox
        mailbox     The mailbox
        source_file The file containing the user information to pull from.
                    Defaults to voicemail.conf

        Returns:
        A VoiceMailMailboxManagement.UserObject object, populated with the
        user's values, or an empty object
        """

        file_path = (self.__ast.base + self.__ast.directories['astetcdir'] +
                     "/" + source_file)

        config_file = ConfigFile(file_path)
        user_object = VoiceMailMailboxManagement.UserObject()
        for cat in config_file.categories:
            if cat.name == context:
                for kvp in cat.options:
                    if kvp[0] == mailbox:
                        tokens = kvp[1].split(',')
                        i = 0
                        for token in tokens:
                            if i == 0:
                                user_object.password = token
                            elif i == 1:
                                user_object.fullname = token
                            elif i == 2:
                                user_object.emailaddress = token
                            elif i == 3:
                                user_object.pageraddress = token
                            i += 1
                        return user_object
        return user_object

    def check_voice_file_exists(self, context, mailbox, name,
                                folder=inbox_folder_name):
        """Checks if a file exists under the voicemail file structure

        Keyword Arguments:
        context    The context of the mailbox
        mailbox    The mailbox
        msgnum     The name of the file to check for
        folder     The folder to check under; default to the default inbox name

        Returns:
        True if the file exists
        False otherwise
        """
        if not (self.check_folder_exists(context, mailbox, folder)):
            return False

        msg_path = (self.__ast.base + "%(vd)s/%(c)s/%(m)s/%(f)s/%(n)s" % {
                    'vd': self.voicemail_directory,
                    'c': context,
                    'm': mailbox,
                    'f': folder,
                    'n': name})

        if (os.path.exists(msg_path)):
            return True
        else:
            return False

    def _remove_items_from_folder(self, mailbox_path, folder):
        """Remove items from the specified mailbox folder"""

        folder_path = os.path.join(self.__ast.base, "%(mp)s/%(f)s" % {
                        'mp': mailbox_path, 'f': folder})
        if not (os.path.exists(folder_path)):
            return

        folder_path = folder_path + '/*'
        for voicemail_file in glob.glob(folder_path):
            if not os.path.isdir(voicemail_file):
                os.remove(voicemail_file)
        return

    def remove_mailbox(self, context, mailbox, remove_folders=False):
        """Removes all items from a mailbox

        Optionally removes the mailbox itself from the file system. This does
        not remove the context folder

        Keyword Arguments:
        context         The context the mailbox exists under
        mailbox         The mailbox to remove
        remove_folders  If true, the folders as well as their contents will be
                        removed

        Returns:
        True on successful removal of the messages/folders
        False otherwise
        """
        mailbox_path = (self.__ast.base + "/%(vd)s/%(c)s/%(m)s" % {
                        'vd': self.voicemail_directory,
                        'c': context,
                        'm': mailbox})

        if not (os.path.exists(mailbox_path)):
            return False

        self._remove_items_from_folder(mailbox_path,
                                       VoiceMailMailboxManagement.inbox_folder_name)
        self._remove_items_from_folder(mailbox_path,
                                       VoiceMailMailboxManagement.temp_folder_name)
        self._remove_items_from_folder(mailbox_path,
                                       VoiceMailMailboxManagement.old_folder_name)
        self._remove_items_from_folder(mailbox_path,
                                       VoiceMailMailboxManagement.urgent_folder_name)
        self._remove_items_from_folder(mailbox_path,
                                       VoiceMailMailboxManagement.greetings_folder_name)

        if (remove_folders):
            os.rmdir(os.path.join(self.__ast.base, "%(mp)s/%(f)s" % {
                    'mp': mailbox_path,
                    'f': VoiceMailMailboxManagement.inbox_folder_name}))
            os.rmdir(os.path.join(self.__ast.base, "%(mp)s/%(f)s" % {
                    'mp': mailbox_path,
                    'f': VoiceMailMailboxManagement.temp_folder_name}))
            os.rmdir(os.path.join(self.__ast.base, "%(mp)s/%(f)s" % {
                    'mp': mailbox_path,
                    'f': VoiceMailMailboxManagement.old_folder_name}))
            os.rmdir(os.path.join(self.__ast.base, "%(mp)s/%(f)s" % {
                    'mp': mailbox_path,
                    'f': VoiceMailMailboxManagement.urgent_folder_name}))
            os.rmdir(os.path.join(self.__ast.base, "%(mp)s/%(f)s" % {
                    'mp': mailbox_path,
                    'f': VoiceMailMailboxManagement.greetings_folder_name}))
            os.rmdir(mailbox_path)

        return True
