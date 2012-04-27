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
import time
import random

from asterisk import Asterisk
from config import Category
from config import ConfigFile
from TestCase import TestCase
from TestState import TestState
from TestState import TestStateController

sys.path.append("lib/python")

logger = logging.getLogger(__name__)


"""
Class that holds the state of some test condition, and allows a callback function to be used to evaluate
whether or not that test condition has passed
"""
class TestCondition(object):

    """
    evaluateFunc    function used to evaluate the condition
    testConditionData    Some piece of data that will be passed to the evaluateFunc

    Note that evaluteFunc should return True or False, and take in two parameters - a value being evaluated
    and the member data testConditionData
    """
    def __init__(self, evaluateFunc = None, testConditionData = None):
        self.__evaluateFunc = evaluateFunc
        self.testConditionData = testConditionData
        self.currentState = False

    """
    Evaluate the test condition

    value    The value to evaluate
    """
    def evaluate(self, value):
        if self.__evaluateFunc != None:
            self.currentState = self.__evaluateFunc(value, self)
        else:
            logger.warn("no evaluate function defined, setting currentState to value")
            self.currentState = value
        return


"""
Base class for voice mail tests that use the TestCase AMI event and the TestStateController
"""
class VoiceMailTest(TestCase):

    """
    The formats a message can be left in
    """
    formats = ["ulaw","wav","WAV"]

    """
    The default expected channel to be used to send info to the voicemail server
    """
    defaultSenderChannel = "SIP/ast1-00000000"

    def __init__(self):
        TestCase.__init__(self)

        self.amiReceiver = None
        self.amiSender = None
        self.astSender = None
        self.__testConditions = {}
        self.__previous_audio = ""
        self.__previous_dtmf = ""
        self.senderChannel = VoiceMailTest.defaultSenderChannel

    """
    Create the test controller.  Should be called once amiReceiver and amiSender have both been set
    """
    def createTestController(self):
        if (self.amiReceiver != None and self.amiSender != None):
            self.testStateController = TestStateController(self, self.amiReceiver)

    def __handleRedirectFailure__(self, reason):
        logger.warn("Error sending redirect - test may or may not fail:")
        logger.warn(reason.getTraceback())
        return reason

    """
    Hangs up the current call
    """
    def hangup(self):
        if self.astSender == None:
            logger.error("Attempting to send hangup to non-existant Asterisk instance")
            self.testStateController.changeState(FailureTestState(self.controller))
            return

        df = self.amiSender.redirect(self.senderChannel, "voicemailCaller", "hangup", 1)
        df.addErrback(self.__handleRedirectFailure__)

    """
    Send a DTMF signal to the voicemail server
    dtmfToSend    The DTMF code to send
    """
    def sendDTMF(self, dtmfToSend):
        logger.info("Attempting to send DTMF " + dtmfToSend)
        if self.amiSender == None:
            logger.error("Attempting to send DTMF to non-connected caller AMI")
            self.testStateController.changeState(FailureTestState(self.controller))
            return

        if (self.__previous_dtmf != dtmfToSend):
            self.amiSender.setVar(channel = "", variable = "DTMF_TO_SEND", value = dtmfToSend)
            self.__previous_dtmf = dtmfToSend

        """
        Redirect to the DTMF extension - note that we assume that we only have one channel to
        the other asterisk instance
        """
        df = self.amiSender.redirect(self.senderChannel, "voicemailCaller", "sendDTMF", 1)
        df.addErrback(self.__handleRedirectFailure__)

    """
    Send a sound file to the voicemail server
    audioFile    The local path to the file to stream
    """
    def sendSoundFile(self, audioFile):
        if self.amiSender == None:
            logger.error("Attempting to send sound file to non-connected caller AMI")
            self.testStateController.changeState(FailureTestState(self.controller))
            return

        if (self.__previous_audio != audioFile):
            self.amiSender.setVar(channel = "", variable = "TALK_AUDIO", value = audioFile)
            self.__previous_audio = audioFile

        """
        Redirect to the send sound file extension - note that we assume that we only have one channel to
        the other asterisk instance
        """
        df = self.amiSender.redirect(self.senderChannel, "voicemailCaller", "sendAudio", 1)
        df.addErrback(self.__handleRedirectFailure__)

    """
    Send a sound file to the voicemail server, then send a DTMF signal
    audioFile    The local path to the file to stream
    dtmfToSend   The DTMF signal to send

    Note that this is necessary so that when the audio file is finished, we close the audio recording cleanly;
    otherwise, Asterisk will detect the end of file as a hangup
    """
    def sendSoundFileWithDTMF(self, audioFile, dtmfToSend):
        if self.amiSender == None:
            logger.error("Attempting to send sound file / DTMF to non-connected caller AMI")
            TestCase.testStateController.changeState(FailureTestState(self.controller))
            return

        if (self.__previous_audio != audioFile):
            self.amiSender.setVar(channel = "", variable = "TALK_AUDIO", value = audioFile)
            self.__previous_audio = audioFile
        if (self.__previous_dtmf != dtmfToSend):
            self.amiSender.setVar(channel = "", variable = "DTMF_TO_SEND", value = dtmfToSend)
            self.__previous_dtmf = dtmfToSend

        """
        Redirect to the send sound file extension - note that we assume that we only have one channel to
        the other asterisk instance
        """
        df = self.amiSender.redirect(self.senderChannel, "voicemailCaller", "sendAudioWithDTMF", 1)
        df.addErrback(self.__handleRedirectFailure__)

    """
    Add a new test condition to track

    conditionName    The unique name of the condition
    condition        The TestCondition object
    """
    def addTestCondition(self, conditionName, condition):
        self.__testConditions[conditionName] = condition

    """
    Set a test condition to the specified value, and evalute whether or not it has passed

    conditionName    The unique name of the condition
    value            The value to pass to the evaluation checker
    """
    def setTestCondition(self, conditionName, value):
        if conditionName in self.__testConditions.keys():
            self.__testConditions[conditionName].evaluate(value)

    """
    Get the current state of a test condition

    conditionName    The unique name of the condition
    returns True if the condition has passed; False otherwise
    """
    def getTestCondition(self, conditionName):
        if conditionName in self.__testConditions.keys():
            return self.__testConditions[conditionName].currentState
        return False

    """
    Check all test conditions

    returns True if all have passed; False if any have not
    """
    def checkTestConditions(self):
        retVal = True
        for k, v in self.__testConditions.items():
            if not v.currentState:
                logger.warn("Test Condition [" + k + "] has not passed") 
                retVal = False

        return retVal

"""
Base class for VoiceMail TestEvent state machine handling

Note - this class exists mostly to share the VoiceMailTest object across the concrete class
implementations
"""
class VoiceMailState(TestState):

    """
    controller        The TestStateController managing the test
    voiceMailTest     The main test object
    """
    def __init__(self, controller, voiceMailTest):
        TestState.__init__(self, controller)
        self.voiceMailTest = voiceMailTest
        if self.voiceMailTest == None:
            logger.error("Failed to set voicemail test object")
            raise RuntimeError('Failed to set voicemail test object')

        logger.debug(" Entering state [" + self.getStateName() + "]")

    """
    Should be overriden by derived classes and return the name of the current state
    """
    def getStateName(self):
        pass

    """
    Can be called by derived classes to output a state that is being ignored
    """
    def handleDefaultState(self, event):
        logger.debug(" State [" + self.getStateName() + "] - ignoring state change " + event['state'])


"""
Class that manages creation of, verification of, and teardown of Asterisk mailboxes on the local filesystem
"""
class VoiceMailMailboxManagement(object):

    """
    Asterisk instance to track
    """
    __ast=None

    """
    Member variable that defines the base location for the voicemail folders
    """
    voicemailDirectory=""

    """
    The parent directory that this test resides in
    """
    testParentDir = "tests/apps/voicemail"

    """
    Name of the folder for new messages
    """
    inboxFolderName="INBOX"

    """
    Name of the folder for temporary messages
    """
    tempFolderName="tmp"

    """
    Name of the folder for old messages
    """
    oldFolderName="Old"

    """
    Name of the folder for urgent messages
    """
    urgentFolderName="Urgent"

    """
    Name of the folder for recorded greetings
    """
    greetingsFolderName="greet"

    """
    Constructor
    ast    The instance of Asterisk to track
    """
    def __init__(self, ast):
        self.__ast = ast
        self.voicemailDirectory = self.__ast.directories['astspooldir'] + '/voicemail'
        self.createdVoicemails = {}

    """
    Creates the basic set of folders needed for a mailbox on the file system
    context    The context that the mailbox will exist under
    mailbox    The mailbox to create
    createAllFolders    Optional parameter that will create all of the various folders.

    In general, app_voicemail should be responsible for making the folders on the file system
    as needed.  This method should only be needed when we want to bypass some of the standard applications
    and create a known state of a voicemail mailbox

    true on success, false on error
    """
    def createMailbox(self, context, mailbox, createAllFolders=False):
        mailboxPath = self.__ast.base + "%(vd)s/%(c)s/%(m)s" %{'vd': self.voicemailDirectory, 'c': context, 'm': mailbox}

        try:
            if not os.path.isdir(mailboxPath):
                os.makedirs(mailboxPath)

            if (createAllFolders):

                inboxPath = "%(mp)s/%(f)s" %{'mp':mailboxPath, 'f':self.inboxFolderName}
                if not os.path.isdir(inboxPath):
                    os.makedirs(inboxPath)

                tempPath = "%(mp)s/%(f)s" %{'mp':mailboxPath, 'f':self.tempFolderName}
                if not os.path.isdir(tempPath):
                    os.makedirs(tempPath)

                oldPath = "%(mp)s/%(f)s" %{'mp':mailboxPath, 'f':self.oldFolderName}
                if not os.path.isdir(oldPath):
                    os.makedirs(oldPath)

                urgentPath = "%(mp)s/%(f)s" %{'mp':mailboxPath, 'f':self.urgentFolderName}
                if not os.path.isdir(urgentPath):
                    os.makedirs(urgentPath)

                greetingsPath = "%(mp)s/%(f)s" %{'mp':mailboxPath, 'f':self.greetingsFolderName}
                if not os.path.isdir(greetingsPath):
                    os.makedirs(greetingsPath)

        except IOError as e:
            if e.errno == errno.EACCESS:
                logger.error( "You do not have sufficient permissions to perform the necessary directory manipulations")
                return False

        return True

    """
    Creates a dummy voicemail in the specified mailbox / folder
    context    The context of the mailbox
    mailbox    The mailbox
    folder     The folder to create the voicemail in
    msgnum     The message number
    formats    The formats to create the sound file as

    The 'formats' merely append particular designators on the end of the sound file,
    /voicemail/sounds/talking.  The actual sound file is not converted.

    True if the voicemail was created successfully, false otherwise
    """
    def createDummyVoicemail(self, context, mailbox, folder, msgnum, formats):
        if not self.checkFolderExists(context, mailbox, folder):
            return False

        msgName = 'msg%04d' % (msgnum)
        msgEnvName = msgName + ".txt"
        msgEnvPath = self.__ast.base + "%(vd)s/%(c)s/%(m)s/%(f)s/%(n)s" % {'vd':self.voicemailDirectory, 'c':context, 'm':mailbox, 'f':folder, 'n':msgEnvName}

        random.seed()
        msg_id = str(int(time.time())) + "-" + str(random.randrange(0, 1, sys.maxint - 1))

        f = open(msgEnvPath, 'w')
        f.write(';\n')
        f.write('; Message Information file\n')
        f.write(';\n')
        f.write('[message]\n')
        f.write('origmailbox=' + mailbox + '\n')
        f.write('context=' + context + '\n')
        f.write('macrocontext=\n')
        f.write('exten=' + mailbox + '\n')
        f.write('rdnis=unknown\n')
        f.write('priority=2\n')
        f.write('callerchan=SIP/ast1-00000000\n')
        f.write('callerid=\"Anonymous\"<555-5555>\n')
        f.write('origdate=Tue Aug  9 10:05:13 PM UTC 2011\n')
        f.write('origtime=1312927513\n')
        f.write('msg_id=%s\n' % msg_id)
        if (folder == self.urgentFolderName):
            f.write('flag=Urgent\n')
        else:
            f.write('flag=\n')
        f.write('category=tt-monkeys\n')
        f.write('duration=6\n')
        f.close()

        for format in formats:
            msgFormatName = msgName + '.' + format
            msgFormatPath = self.__ast.base + "%(vd)s/%(c)s/%(m)s/%(f)s/%(n)s" % {'vd':self.voicemailDirectory, 'c':context, 'm':mailbox, 'f':folder, 'n':msgFormatName}
            audioFile = os.path.join(os.getcwd(), "%s/sounds/talking.ulaw" % (self.testParentDir))
            shutil.copy(audioFile, msgFormatPath)

        if folder not in self.createdVoicemails.keys():
            self.createdVoicemails[folder] = []
        self.createdVoicemails[folder].append((msgnum, msg_id))

        return True

    """
    Checks that a folder exists for a particular user
    context    The context of the mailbox
    mailbox    The mailbox
    folder     The folder to check; defaults to the default inbox name

    true if the folder exists, false otherwise
    """
    def checkFolderExists(self, context, mailbox, folder=inboxFolderName):
        mailboxPath = self.__ast.base + "%(vd)s/%(c)s/%(m)s" %{'vd': self.voicemailDirectory, 'c': context, 'm': mailbox}

        if not (os.path.exists(mailboxPath)):
            return False

        folderPath = "%(mp)s/%(f)s" %{'mp':mailboxPath, 'f':folder}

        return os.path.exists(folderPath)

    """
    Check if a voicemail exists on the filesystem
    context    The context of the mailbox
    mailbox    The mailbox
    msgnum     The 1-based index of the voicemail to check for
    lstFormats The formats we expect to be recorded for us
    folder     The folder to check under; default to the default inbox name

    true if the voicemail exists, false otherwise
    """
    def checkVoicemailExists(self, context, mailbox, msgnum, lstFormats, folder=inboxFolderName):
        retVal = True

        """ construct the expected base file name
        """
        msgName = 'msg%04d' % (msgnum)

        for format in lstFormats:
            fileName = msgName + "." + format
            retVal = retVal & self.checkVoiceFileExists(context, mailbox, fileName, folder)

        """ make sure we have the message envelope file
        """
        fileName = msgName + ".txt"
        retVal = retVal & self.checkVoiceFileExists(context, mailbox, fileName, folder)

        return retVal

    """
    Check if a voicemail greeting exists on the filesystem
    context    The context of the mailbox
    mailbox    The mailbox
    msgname    The name of the greeting to find
    lstFormats The formats we expect to be recorded for us

    true if the greeting exists, false otherwise
    """
    def checkGreetingExists(self, context, mailbox, msgname, lstFormats):
        retVal = True

        for format in lstFormats:
            fileName = msgname + "." + format
            retVal = retVal & self.checkVoiceFileExists(context, mailbox, fileName, "")

        return retVal

    """
    Check if a voicemail has the property specified
    context    The context of the mailbox
    mailbox    The mailbox
    msgnum     The 1-based index of the voicemail to check for
    propertyName    The name of the property to check
    propertyValue    The value to check for
    folder    The folder to check under; default to the default inbox name

    true if the voicemail has the property and value specified; false otherwise
    """
    def checkVoicemailProperty(self, context, mailbox, msgnum, propertyName, propertyValue, folder=inboxFolderName):
        lstFormats = []
        if not self.checkVoicemailExists(context, mailbox, msgnum, lstFormats, folder):
            return False

        msgName = 'msg%(msgnum)04d' %{"msgnum":msgnum}
        msgName = msgName + ".txt"
        msgPath = self.__ast.base + "%(vd)s/%(c)s/%(m)s/%(f)s/%(n)s" % {'vd':self.voicemailDirectory, 'c':context, 'm':mailbox, 'f':folder, 'n':msgName}

        configFile = ConfigFile(msgPath)
        for cat in configFile.categories:
            if cat.name == 'message':
                for kvp in cat.options:
                    if kvp[0] == propertyName and kvp[1] == propertyValue:
                        return True

        return False

    """
    An object that holds voicemail user information
    """
    class UserObject(object):
        def __init__(self):
            self.password = ""
            self.fullname = ""
            self.emailaddress = ""
            self.pageraddress = ""

    """
    Gets user information from the voicemail configuration file

    context    The context of the mailbox
    mailbox    The mailbox
    sourceFile    The file containing the user information to pull from.  Defaults
        to voicemail.conf

    returns A VoiceMailMailboxManagement.UserObject object, populated with the user's values,
        or an empty object
    """
    def getUserObject(self, context, mailbox, sourceFile="voicemail.conf"):

        filePath = self.__ast.base + self.__ast.directories['astetcdir'] + "/" + sourceFile

        configFile = ConfigFile(filePath)
        userObject = VoiceMailMailboxManagement.UserObject()
        for cat in configFile.categories:
            if cat.name == context:
                for kvp in cat.options:
                    if kvp[0] == mailbox:
                        tokens = kvp[1].split(',')
                        i = 0
                        for token in tokens:
                            if i == 0:
                                userObject.password = token
                            elif i == 1:
                                userObject.fullname = token
                            elif i == 2:
                                userObject.emailaddress = token
                            elif i == 3:
                                userObject.pageraddress = token
                            i += 1
                        return userObject

        return userObject

    """
    Checks if a file exists under the voicemail file structure
    context    The context of the mailbox
    mailbox    The mailbox
    msgnum     The name of the file to check for
    folder     The folder to check under; default to the default inbox name

    true if the file exists, false otherwise
    """
    def checkVoiceFileExists(self, context, mailbox, name, folder=inboxFolderName):
        if not (self.checkFolderExists(context, mailbox, folder)):
            return False

        msgPath = self.__ast.base + "%(vd)s/%(c)s/%(m)s/%(f)s/%(n)s" % {'vd':self.voicemailDirectory, 'c':context, 'm':mailbox, 'f':folder, 'n':name}

        if (os.path.exists(msgPath)):
            return True
        else:
            return False

    def __removeItemsFromFolder__(self, mailboxPath, folder):
        folderPath = os.path.join(self.__ast.base, "%(mp)s/%(f)s" % {'mp':mailboxPath, 'f':folder})

        if not (os.path.exists(folderPath)):
            return

        folderPath = folderPath + '/*'
        for voicemailFile in glob.glob(folderPath):
            if not os.path.isdir(voicemailFile):
                os.remove(voicemailFile)

        return

    """
    Removes all items from a mailbox, and optionally removes the mailbox itself from the file system
    context    The context the mailbox exists under
    mailbox    The mailbox to remove
    removeFolders    If true, the folders as well as their contents will be removed

    This does not remove the context folder

    False if the mailbox does not exist, otherwise True
    """
    def removeMailbox(self, context, mailbox, removeFolders=False):
        mailboxPath = self.__ast.base + "/%(vd)s/%(c)s/%(m)s" %{'vd': self.voicemailDirectory, 'c': context, 'm': mailbox}

        if not (os.path.exists(mailboxPath)):
            return False

        self.__removeItemsFromFolder__(mailboxPath, self.inboxFolderName)
        self.__removeItemsFromFolder__(mailboxPath, self.tempFolderName)
        self.__removeItemsFromFolder__(mailboxPath, self.oldFolderName)
        self.__removeItemsFromFolder__(mailboxPath, self.urgentFolderName)
        self.__removeItemsFromFolder__(mailboxPath, self.greetingsFolderName)

        if (removeFolders):
            rmdir(os.path.join(self.__ast.base, "%(mp)s/%(f)s" %{'mp':mailboxPath, 'f':self.inboxFolderName}))
            rmdir(os.path.join(self.__ast.base, "%(mp)s/%(f)s" %{'mp':mailboxPath, 'f':self.tempFolderName}))
            rmdir(os.path.join(self.__ast.base, "%(mp)s/%(f)s" %{'mp':mailboxPath, 'f':self.oldFolderName}))
            rmdir(os.path.join(self.__ast.base, "%(mp)s/%(f)s" %{'mp':mailboxPath, 'f':self.urgentFolderName}))
            rmdir(os.path.join(self.__ast.base, "%(mp)s/%(f)s" %{'mp':mailboxPath, 'f':self.greetingsFolderName}))

            rmdir(mailboxPath)

        return True

