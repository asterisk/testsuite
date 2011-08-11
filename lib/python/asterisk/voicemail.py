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

from asterisk import Asterisk
from config import Category
from config import ConfigFile

sys.path.append("lib/python")

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
        mailboxPath = self.__ast.baseDirectory + "%(vd)s/%(c)s/%(m)s" %{'vd': self.voicemailDirectory, 'c': context, 'm': mailbox}

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
                print "You do not have sufficient permissions to perform the necessary directory manipulations"
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
        msgEnvPath = self.__ast.baseDirectory + "%(vd)s/%(c)s/%(m)s/%(f)s/%(n)s" % {'vd':self.voicemailDirectory, 'c':context, 'm':mailbox, 'f':folder, 'n':msgEnvName}

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
        f.write('callerid=\"Anonymous\"<ast1>\n')
        f.write('origdate=Tue Aug  9 10:05:13 PM UTC 2011\n')
        f.write('origtime=1312927513\n')
        if (folder == self.urgentFolderName):
            f.write('flag=Urgent\n')
        else:
            f.write('flag=\n')
        f.write('duration=1\n')
        f.close()

        for format in formats:
            msgFormatName = msgName + '.' + format
            msgFormatPath = self.__ast.baseDirectory + "%(vd)s/%(c)s/%(m)s/%(f)s/%(n)s" % {'vd':self.voicemailDirectory, 'c':context, 'm':mailbox, 'f':folder, 'n':msgFormatName}
            audioFile = os.path.join(os.getcwd(), "%s/sounds/talking.ulaw" % (self.testParentDir))
            shutil.copy(audioFile, msgFormatPath)

        return True

    """
    Checks that a folder exists for a particular user
    context    The context of the mailbox
    mailbox    The mailbox
    folder     The folder to check; defaults to the default inbox name

    true if the folder exists, false otherwise
    """
    def checkFolderExists(self, context, mailbox, folder=inboxFolderName):
        mailboxPath = self.__ast.baseDirectory + "%(vd)s/%(c)s/%(m)s" %{'vd': self.voicemailDirectory, 'c': context, 'm': mailbox}

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
        msgPath = self.__ast.baseDirectory + "%(vd)s/%(c)s/%(m)s/%(f)s/%(n)s" % {'vd':self.voicemailDirectory, 'c':context, 'm':mailbox, 'f':folder, 'n':msgName}

        configFile = ConfigFile(msgPath)
        for cat in configFile.categories:
            if cat.name == 'message':
                for kvp in cat.options:
                    if kvp[0] == propertyName and kvp[1] == propertyValue:
                        return True

        return False

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

        msgPath = self.__ast.baseDirectory + "%(vd)s/%(c)s/%(m)s/%(f)s/%(n)s" % {'vd':self.voicemailDirectory, 'c':context, 'm':mailbox, 'f':folder, 'n':name}

        if (os.path.exists(msgPath)):
            return True
        else:
            return False


    def __removeItemsFromFolder__(self, mailboxPath, folder):
        folderPath = os.path.join(self.__ast.baseDirectory, "%(mp)s/%(f)s" % {'mp':mailboxPath, 'f':folder})

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
        mailboxPath = self.__ast.baseDirectory + "/%(vd)s/%(c)s/%(m)s" %{'vd': self.voicemailDirectory, 'c': context, 'm': mailbox}

        if not (os.path.exists(mailboxPath)):
            return False

        self.__removeItemsFromFolder__(mailboxPath, self.inboxFolderName)
        self.__removeItemsFromFolder__(mailboxPath, self.tempFolderName)
        self.__removeItemsFromFolder__(mailboxPath, self.oldFolderName)
        self.__removeItemsFromFolder__(mailboxPath, self.urgentFolderName)
        self.__removeItemsFromFolder__(mailboxPath, self.greetingsFolderName)

        if (removeFolders):
            rmdir(os.path.join(self.__ast.baseDirectory, "%(mp)s/%(f)s" %{'mp':mailboxPath, 'f':self.inboxFolderName}))
            rmdir(os.path.join(self.__ast.baseDirectory, "%(mp)s/%(f)s" %{'mp':mailboxPath, 'f':self.tempFolderName}))
            rmdir(os.path.join(self.__ast.baseDirectory, "%(mp)s/%(f)s" %{'mp':mailboxPath, 'f':self.oldFolderName}))
            rmdir(os.path.join(self.__ast.baseDirectory, "%(mp)s/%(f)s" %{'mp':mailboxPath, 'f':self.urgentFolderName}))
            rmdir(os.path.join(self.__ast.baseDirectory, "%(mp)s/%(f)s" %{'mp':mailboxPath, 'f':self.greetingsFolderName}))

            rmdir(mailboxPath)

        return True

