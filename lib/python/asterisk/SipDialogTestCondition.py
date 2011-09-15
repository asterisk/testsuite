#!/usr/bin/env python
'''
Copyright (C) 2011, Digium, Inc.
Matt Jordan <mjordan@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
'''

import logging
import logging.config
import time
import unittest

from TestConditions import TestCondition
from starpy import manager

logger = logging.getLogger(__name__)

class SipDialogTestCondition(TestCondition):
    """
    This class is a base class for the pre- and post-test condition
    classes that check for the existance of SIP dialogs in Asterisk.  It provides common
    functionality for parsing out the results of the 'sip show objects' and
    'sip show history' Asterisk commands
    """

    def __init__(self, test_config):
        super(SipDialogTestCondition, self).__init__(test_config)

    def __get_dialog_names(self, objects):
        inObjects = False
        objectList = objects.split('\n')
        dialogNames = []
        for o in objectList:
            if "Dialog objects" in o:
                inObjects = True
            if "name:" in o and inObjects:
                dialogNames.append(o[o.find(":")+1:].strip())
        return dialogNames

    def get_sip_dialogs(self, ast):
        dialogNames = []
        dialogsHistory = {}
        objects = ast.cli_exec("sip show objects", True)
        dialogNames = self.__get_dialog_names(objects)

        for dn in dialogNames:
            logger.debug("Retrieving history for SIP dialog %s" % dn)
            rawHistory = ast.cli_exec("sip show history %s" % dn, True)
            if 'No such SIP Call ID' not in rawHistory:
                """ dialog got disposed before we could get its history; ignore """
                dialogsHistory[dn] = rawHistory.split('\n')

        return dialogsHistory

class SipDialogPreTestCondition(SipDialogTestCondition):
    """
    Check the pre-test conditions for SIP dialogs.  This test simply
    checks that there are no SIP dialogs present before test execution.
    """

    def __init__(self, test_config):
        super(SipDialogPreTestCondition, self).__init__(test_config)

    def evaluate(self, related_test_condition = None):
        for ast in self.ast:
            ast.cli_exec("sip set history on")
            dialogsHistory = super(SipDialogPreTestCondition, self).get_sip_dialogs(ast)

            if len(dialogsHistory) > 0:
                """ If any dialogs are present before test execution, something funny is going on """
                super(SipDialogPreTestCondition, self).failCheck(
                    "%d dialogs were detected in Asterisk %s before test execution" % (len(dialogsHistory), ast.host))
            else:
                super(SipDialogPreTestCondition, self).passCheck()


class SipDialogPostTestCondition(SipDialogTestCondition):
    """
    Check the post-test conditions for SIP dialogs.  This test looks for
    any SIP dialogs still in existence.  If it does not detect any, the test
    passes.  If it does detect dialogs, it checks to make sure that the dialogs
    have been hungup and are scheduled for destruction.  If those two conditions
    are met, the test passes; otherwise it fails.

    Note: as a future enhancement, implement an AMI command that will force
    garbage collection on the SIP dialogs.  We can then also check that the scheduler
    properly collects SIP dialogs as part of this test.
    """

    def __init__(self, test_config):
        super(SipDialogPostTestCondition, self).__init__(test_config)

        self.sipHistorySequence = []
        if 'sipHistoryRequirements' in test_config.config:
            self.sipHistorySequence = test_config.config['sipHistoryRequirements']

    def evaluate(self, related_test_condition = None):

        for ast in self.ast:
            sipHistoryRequirements = {}
            dialogsHistory = super(SipDialogPostTestCondition, self).get_sip_dialogs(ast)

            """ Set up the history statements to look for in each dialog history """
            for dialogName in dialogsHistory.keys():
                sipHistoryCheck = {}
                for h in self.sipHistorySequence:
                    sipHistoryCheck[h] = False
                sipHistoryRequirements[dialogName] = sipHistoryCheck

            """ Assume we pass the check.  This will be overriden if any history check fails """
            super(SipDialogPostTestCondition, self).passCheck()
            if (len(dialogsHistory) > 0):
                for dialog, history in dialogsHistory.items():
                    scheduled = False
                    for h in history:
                        if "SchedDestroy" in h:
                            scheduled = True
                        for req in sipHistoryRequirements[dialog].keys():
                            if req in h:
                                sipHistoryRequirements[dialog][req] = True

                    if not scheduled:
                        super(SipDialogPostTestCondition, self).failCheck(
                            "Dialog %s in Asterisk instance %s not scheduled for destruction" % (dialog, ast.host))
                    for req in sipHistoryRequirements[dialog].keys():
                        if sipHistoryRequirements[dialog][req] == False:
                            super(SipDialogPostTestCondition, self).failCheck(
                                "Dialog %s in Asterisk instance %s did not have required step in history: %s" % (dialog, ast.host, req))

class TestConfig(object):
    def __init__(self):
        """ Values here don't matter much - we just need to have something """
        self.classTypeName = "asterisk.SipDialogTestCondition.SipDialogPostTestCondition"
        self.passExpected = True
        self.type = "Post"
        self.relatedCondition = ""
        self.config = {}

class TestConfigWithHistory(TestConfig):
    def __init__(self):
        super(TestConfigWithHistory, self).__init__()
        """ Values here don't matter much - we just need to have something """
        tempList = []
        self.config['sipHistoryRequirements'] = tempList
        self.config['sipHistoryRequirements'].append('Hangup') 
        self.config['sipHistoryRequirements'].append('NewChan')

class AstMockObjectPostTestNoDestructionFail(object):
    def __init__(self):
        self.host = "127.0.0.6"

    def cli_exec(self, command, sync = True):
        retString = ""
        if command == "sip show objects":
            retString = "-= Peer objects: 4 static, 0 realtime, 0 autocreate =-\n\n"
            retString += "name: audio\ntype: peer\nobjflags: 0\nrefcount: 3\n\n"
            retString += "name: 7002\ntype: peer\nobjflags: 0\nrefcount: 3\n\n"
            retString += "name: 7001\ntype: peer\nobjflags: 0\nrefcount: 1\n\n"
            retString += "name: zoiper_01\ntype: peer\nobjflags: 0\nrefcount: 3\n\n"
            retString += "-= Peer objects by IP =-\n\n"
            retString += "name: zoiper_01\ntype: peer\nobjflags: 0\nrefcount: 3\n\n"
            retString += "name: audio\ntype: peer\nobjflags: 0\nrefcount: 3\n\n"
            retString += "name: 7002\ntype: peer\nobjflags: 0\nrefcount: 3\n\n"
            retString += "-= Registry objects: 0 =-\n\n"
            retString += "-= Dialog objects:\n\n"
            retString += "name: 2ec048aa4ed1239664f6408f0c5044c4@127.0.0.2:5060\n"
            retString += "type: dialog\n"
            retString += "objflags: 0\n"
            retString += "refcount: 2\n\n"
            retString += "name: 2ec048aa4ed1239664f6408f0c5044c5@127.0.0.2:5060\n"
            retString += "type: dialog\n"
            retString += "objflags: 0\n"
            retString += "refcount: 2\n\n"
        elif command == "sip show history 2ec048aa4ed1239664f6408f0c5044c4@127.0.0.2:5060":
            retString = "* SIP Call\n"
            retString += "1. NewChan         Channel SIP/ast1-00000002 - from 2ec048aa4ed1239664f6408f0c5044\n"
            retString += "2. TxReqRel        INVITE / 102 INVITE - INVITE\n"
            retString += "3. Rx              SIP/2.0 / 102 INVITE / 100 Trying\n"
            retString += "4. Rx              SIP/2.0 / 102 INVITE / 200 OK\n"
            retString += "5. TxReq           ACK / 102 ACK - ACK\n"
            retString += "6. Rx              BYE / 102 BYE / sip:ast2@127.0.0.2:5060\n"
            retString += "7. RTCPaudio       Quality:ssrc=28249381;themssrc=485141946;lp=0;rxjitter=0.000029\n"
            retString += "8. RTCPaudioJitter Quality:minrxjitter=0.000000;maxrxjitter=0.000000;avgrxjitter=0\n"
            retString += "9. RTCPaudioLoss   Quality:minrxlost=0.000000;maxrxlost=0.000000;avgrxlost=0.00000\n"
            retString += "10. RTCPaudioRTT    Quality:minrtt=0.000000;maxrtt=0.000000;avgrtt=0.000000;stdevrt\n"
            retString += "11. SchedDestroy    32000 ms\n"
            retString += "12. TxResp          SIP/2.0 / 102 BYE - 200 OK\n"
            retString += "13. Hangup          Cause Normal Clearing\n"
        elif command == "sip show history 2ec048aa4ed1239664f6408f0c5044c5@127.0.0.2:5060":
            retString = "* SIP Call\n"
            retString += "1. NewChan         Channel SIP/ast1-00000002 - from 2ec048aa4ed1239664f6408f0c5044\n"
            retString += "2. TxReqRel        INVITE / 102 INVITE - INVITE\n"
            retString += "3. Rx              SIP/2.0 / 102 INVITE / 100 Trying\n"
            retString += "4. Rx              SIP/2.0 / 102 INVITE / 200 OK\n"
            retString += "5. TxReq           ACK / 102 ACK - ACK\n"
            retString += "6. Rx              BYE / 102 BYE / sip:ast2@127.0.0.2:5060\n"
            retString += "7. RTCPaudio       Quality:ssrc=28249381;themssrc=485141946;lp=0;rxjitter=0.000029\n"
            retString += "8. RTCPaudioJitter Quality:minrxjitter=0.000000;maxrxjitter=0.000000;avgrxjitter=0\n"
            retString += "9. RTCPaudioLoss   Quality:minrxlost=0.000000;maxrxlost=0.000000;avgrxlost=0.00000\n"
            retString += "10. RTCPaudioRTT    Quality:minrtt=0.000000;maxrtt=0.000000;avgrtt=0.000000;stdevrt\n"
            retString += "11. TxResp          SIP/2.0 / 102 BYE - 200 OK\n"
            retString += "12. Hangup          Cause Normal Clearing\n"
        return retString

class AstMockObjectPostTestNoHangupFail(object):
    def __init__(self):
        self.host = "127.0.0.5"

    def cli_exec(self, command, sync = True):
        retString = ""
        if command == "sip show objects":
            retString = "-= Peer objects: 4 static, 0 realtime, 0 autocreate =-\n\n"
            retString += "name: audio\ntype: peer\nobjflags: 0\nrefcount: 3\n\n"
            retString += "name: 7002\ntype: peer\nobjflags: 0\nrefcount: 3\n\n"
            retString += "name: 7001\ntype: peer\nobjflags: 0\nrefcount: 1\n\n"
            retString += "name: zoiper_01\ntype: peer\nobjflags: 0\nrefcount: 3\n\n"
            retString += "-= Peer objects by IP =-\n\n"
            retString += "name: zoiper_01\ntype: peer\nobjflags: 0\nrefcount: 3\n\n"
            retString += "name: audio\ntype: peer\nobjflags: 0\nrefcount: 3\n\n"
            retString += "name: 7002\ntype: peer\nobjflags: 0\nrefcount: 3\n\n"
            retString += "-= Registry objects: 0 =-\n\n"
            retString += "-= Dialog objects:\n\n"
            retString += "name: 2ec048aa4ed1239664f6408f0c5044c4@127.0.0.2:5060\n"
            retString += "type: dialog\n"
            retString += "objflags: 0\n"
            retString += "refcount: 2\n\n"
            retString += "name: 2ec048aa4ed1239664f6408f0c5044c5@127.0.0.2:5060\n"
            retString += "type: dialog\n"
            retString += "objflags: 0\n"
            retString += "refcount: 2\n\n"
        elif command == "sip show history 2ec048aa4ed1239664f6408f0c5044c4@127.0.0.2:5060":
            retString = "* SIP Call\n"
            retString += "1. NewChan         Channel SIP/ast1-00000002 - from 2ec048aa4ed1239664f6408f0c5044\n"
            retString += "2. TxReqRel        INVITE / 102 INVITE - INVITE\n"
            retString += "3. Rx              SIP/2.0 / 102 INVITE / 100 Trying\n"
            retString += "4. Rx              SIP/2.0 / 102 INVITE / 200 OK\n"
            retString += "5. TxReq           ACK / 102 ACK - ACK\n"
            retString += "6. Rx              BYE / 102 BYE / sip:ast2@127.0.0.2:5060\n"
            retString += "7. RTCPaudio       Quality:ssrc=28249381;themssrc=485141946;lp=0;rxjitter=0.000029\n"
            retString += "8. RTCPaudioJitter Quality:minrxjitter=0.000000;maxrxjitter=0.000000;avgrxjitter=0\n"
            retString += "9. RTCPaudioLoss   Quality:minrxlost=0.000000;maxrxlost=0.000000;avgrxlost=0.00000\n"
            retString += "10. RTCPaudioRTT    Quality:minrtt=0.000000;maxrtt=0.000000;avgrtt=0.000000;stdevrt\n"
            retString += "11. SchedDestroy    32000 ms\n"
            retString += "12. TxResp          SIP/2.0 / 102 BYE - 200 OK\n"
        elif command == "sip show history 2ec048aa4ed1239664f6408f0c5044c5@127.0.0.2:5060":
            retString = "* SIP Call\n"
            retString += "1. NewChan         Channel SIP/ast1-00000002 - from 2ec048aa4ed1239664f6408f0c5044\n"
            retString += "2. TxReqRel        INVITE / 102 INVITE - INVITE\n"
            retString += "3. Rx              SIP/2.0 / 102 INVITE / 100 Trying\n"
            retString += "4. Rx              SIP/2.0 / 102 INVITE / 200 OK\n"
            retString += "5. TxReq           ACK / 102 ACK - ACK\n"
            retString += "6. Rx              BYE / 102 BYE / sip:ast2@127.0.0.2:5060\n"
            retString += "7. RTCPaudio       Quality:ssrc=28249381;themssrc=485141946;lp=0;rxjitter=0.000029\n"
            retString += "8. RTCPaudioJitter Quality:minrxjitter=0.000000;maxrxjitter=0.000000;avgrxjitter=0\n"
            retString += "9. RTCPaudioLoss   Quality:minrxlost=0.000000;maxrxlost=0.000000;avgrxlost=0.00000\n"
            retString += "10. RTCPaudioRTT    Quality:minrtt=0.000000;maxrtt=0.000000;avgrtt=0.000000;stdevrt\n"
            retString += "11. SchedDestroy    32000 ms\n"
            retString += "12. TxResp          SIP/2.0 / 102 BYE - 200 OK\n"
            retString += "13. Hangup          Cause Normal Clearing\n"
        return retString

class AstMockObjectPostTestNoDialogsPass(object):
    def __init__(self):
        self.host = "127.0.0.4"

    def cli_exec(self, command, sync = True):
        retString = ""
        if command == "sip show objects":
            retString = "-= Peer objects: 4 static, 0 realtime, 0 autocreate =-\n\n"
            retString += "name: audio\ntype: peer\nobjflags: 0\nrefcount: 3\n\n"
            retString += "name: 7002\ntype: peer\nobjflags: 0\nrefcount: 3\n\n"
            retString += "name: 7001\ntype: peer\nobjflags: 0\nrefcount: 1\n\n"
            retString += "name: zoiper_01\ntype: peer\nobjflags: 0\nrefcount: 3\n\n"
            retString += "-= Peer objects by IP =-\n\n"
            retString += "name: zoiper_01\ntype: peer\nobjflags: 0\nrefcount: 3\n\n"
            retString += "name: audio\ntype: peer\nobjflags: 0\nrefcount: 3\n\n"
            retString += "name: 7002\ntype: peer\nobjflags: 0\nrefcount: 3\n\n"
            retString += "-= Registry objects: 0 =-\n\n"
            retString += "-= Dialog objects:\n\n"

        return retString

class AstMockObjectPostTestPass(object):
    def __init__(self):
        self.host = "127.0.0.3"

    def cli_exec(self, command, sync = True):
        retString = ""
        if command == "sip show objects":
            retString = "-= Peer objects: 4 static, 0 realtime, 0 autocreate =-\n\n"
            retString += "name: audio\ntype: peer\nobjflags: 0\nrefcount: 3\n\n"
            retString += "name: 7002\ntype: peer\nobjflags: 0\nrefcount: 3\n\n"
            retString += "name: 7001\ntype: peer\nobjflags: 0\nrefcount: 1\n\n"
            retString += "name: zoiper_01\ntype: peer\nobjflags: 0\nrefcount: 3\n\n"
            retString += "-= Peer objects by IP =-\n\n"
            retString += "name: zoiper_01\ntype: peer\nobjflags: 0\nrefcount: 3\n\n"
            retString += "name: audio\ntype: peer\nobjflags: 0\nrefcount: 3\n\n"
            retString += "name: 7002\ntype: peer\nobjflags: 0\nrefcount: 3\n\n"
            retString += "-= Registry objects: 0 =-\n\n"
            retString += "-= Dialog objects:\n\n"
            retString += "name: 2ec048aa4ed1239664f6408f0c5044c4@127.0.0.2:5060\n"
            retString += "type: dialog\n"
            retString += "objflags: 0\n"
            retString += "refcount: 2\n\n"
            retString += "name: 2ec048aa4ed1239664f6408f0c5044c5@127.0.0.2:5060\n"
            retString += "type: dialog\n"
            retString += "objflags: 0\n"
            retString += "refcount: 2\n\n"
        elif command == "sip show history 2ec048aa4ed1239664f6408f0c5044c4@127.0.0.2:5060":
            retString = "* SIP Call\n"
            retString += "1. NewChan         Channel SIP/ast1-00000002 - from 2ec048aa4ed1239664f6408f0c5044\n"
            retString += "2. TxReqRel        INVITE / 102 INVITE - INVITE\n"
            retString += "3. Rx              SIP/2.0 / 102 INVITE / 100 Trying\n"
            retString += "4. Rx              SIP/2.0 / 102 INVITE / 200 OK\n"
            retString += "5. TxReq           ACK / 102 ACK - ACK\n"
            retString += "6. Rx              BYE / 102 BYE / sip:ast2@127.0.0.2:5060\n"
            retString += "7. RTCPaudio       Quality:ssrc=28249381;themssrc=485141946;lp=0;rxjitter=0.000029\n"
            retString += "8. RTCPaudioJitter Quality:minrxjitter=0.000000;maxrxjitter=0.000000;avgrxjitter=0\n"
            retString += "9. RTCPaudioLoss   Quality:minrxlost=0.000000;maxrxlost=0.000000;avgrxlost=0.00000\n"
            retString += "10. RTCPaudioRTT    Quality:minrtt=0.000000;maxrtt=0.000000;avgrtt=0.000000;stdevrt\n"
            retString += "11. SchedDestroy    32000 ms\n"
            retString += "12. TxResp          SIP/2.0 / 102 BYE - 200 OK\n"
            retString += "13. Hangup          Cause Normal Clearing\n"
        elif command == "sip show history 2ec048aa4ed1239664f6408f0c5044c5@127.0.0.2:5060":
            retString = "* SIP Call\n"
            retString += "1. NewChan         Channel SIP/ast1-00000002 - from 2ec048aa4ed1239664f6408f0c5044\n"
            retString += "2. TxReqRel        INVITE / 102 INVITE - INVITE\n"
            retString += "3. Rx              SIP/2.0 / 102 INVITE / 100 Trying\n"
            retString += "4. Rx              SIP/2.0 / 102 INVITE / 200 OK\n"
            retString += "5. TxReq           ACK / 102 ACK - ACK\n"
            retString += "6. Rx              BYE / 102 BYE / sip:ast2@127.0.0.2:5060\n"
            retString += "7. RTCPaudio       Quality:ssrc=28249381;themssrc=485141946;lp=0;rxjitter=0.000029\n"
            retString += "8. RTCPaudioJitter Quality:minrxjitter=0.000000;maxrxjitter=0.000000;avgrxjitter=0\n"
            retString += "9. RTCPaudioLoss   Quality:minrxlost=0.000000;maxrxlost=0.000000;avgrxlost=0.00000\n"
            retString += "10. RTCPaudioRTT    Quality:minrtt=0.000000;maxrtt=0.000000;avgrtt=0.000000;stdevrt\n"
            retString += "11. SchedDestroy    32000 ms\n"
            retString += "12. TxResp          SIP/2.0 / 102 BYE - 200 OK\n"
            retString += "13. Hangup          Cause Normal Clearing\n"
        return retString

class AstMockObjectPreTestFail(object):
    def __init__(self):
        self.host = "127.0.0.2"

    def cli_exec(self, command, sync = True):
        retString = ""
        if command == "sip show objects":
            retString = "-= Peer objects: 4 static, 0 realtime, 0 autocreate =-\n\n"
            retString += "name: audio\ntype: peer\nobjflags: 0\nrefcount: 3\n\n"
            retString += "name: 7002\ntype: peer\nobjflags: 0\nrefcount: 3\n\n"
            retString += "name: 7001\ntype: peer\nobjflags: 0\nrefcount: 1\n\n"
            retString += "name: zoiper_01\ntype: peer\nobjflags: 0\nrefcount: 3\n\n"
            retString += "-= Peer objects by IP =-\n\n"
            retString += "name: zoiper_01\ntype: peer\nobjflags: 0\nrefcount: 3\n\n"
            retString += "name: audio\ntype: peer\nobjflags: 0\nrefcount: 3\n\n"
            retString += "name: 7002\ntype: peer\nobjflags: 0\nrefcount: 3\n\n"
            retString += "-= Registry objects: 0 =-\n\n"
            retString += "-= Dialog objects:\n\n"
            retString += "name: 2ec048aa4ed1239664f6408f0c5044c4@127.0.0.2:5060\n"
            retString += "type: dialog\n"
            retString += "objflags: 0\n"
            retString += "refcount: 2\n\n"
        elif command == "sip show history 2ec048aa4ed1239664f6408f0c5044c4@127.0.0.2:5060":
            retString = "* SIP Call\n"
            retString += "1. NewChan         Channel SIP/ast1-00000002 - from 2ec048aa4ed1239664f6408f0c5044\n"
            retString += "2. TxReqRel        INVITE / 102 INVITE - INVITE\n"
            retString += "3. Rx              SIP/2.0 / 102 INVITE / 100 Trying\n"
            retString += "4. Rx              SIP/2.0 / 102 INVITE / 200 OK\n"
            retString += "5. TxReq           ACK / 102 ACK - ACK\n"
            retString += "6. Rx              BYE / 102 BYE / sip:ast2@127.0.0.2:5060\n"
            retString += "7. RTCPaudio       Quality:ssrc=28249381;themssrc=485141946;lp=0;rxjitter=0.000029\n"
            retString += "8. RTCPaudioJitter Quality:minrxjitter=0.000000;maxrxjitter=0.000000;avgrxjitter=0\n"
            retString += "9. RTCPaudioLoss   Quality:minrxlost=0.000000;maxrxlost=0.000000;avgrxlost=0.00000\n"
            retString += "10. RTCPaudioRTT    Quality:minrtt=0.000000;maxrtt=0.000000;avgrtt=0.000000;stdevrt\n"
            retString += "11. SchedDestroy    32000 ms\n"
            retString += "12. TxResp          SIP/2.0 / 102 BYE - 200 OK\n"
            retString += "13. Hangup          Cause Normal Clearing\n"
        return retString

class AstMockObjectPreTestPass(object):
    def __init__(self):
        self.host = "127.0.0.1"

    def cli_exec(self, command, sync = True):
        retString = ""
        if command == "sip show objects":
            retString = "-= Peer objects: 4 static, 0 realtime, 0 autocreate =-\n\n"
            retString += "name: audio\ntype: peer\nobjflags: 0\nrefcount: 3\n\n"
            retString += "name: 7002\ntype: peer\nobjflags: 0\nrefcount: 3\n\n"
            retString += "name: 7001\ntype: peer\nobjflags: 0\nrefcount: 1\n\n"
            retString += "name: zoiper_01\ntype: peer\nobjflags: 0\nrefcount: 3\n\n"
            retString += "-= Peer objects by IP =-\n\n"
            retString += "name: zoiper_01\ntype: peer\nobjflags: 0\nrefcount: 3\n\n"
            retString += "name: audio\ntype: peer\nobjflags: 0\nrefcount: 3\n\n"
            retString += "name: 7002\ntype: peer\nobjflags: 0\nrefcount: 3\n\n"
            retString += "-= Registry objects: 0 =-\n\n"
            retString += "-= Dialog objects:\n"
        elif command == "sip show history":
            return "\n"
        return retString


class SipDialogTestConditionUnitTest(unittest.TestCase):
    def test_pre_test_pass(self):
        ast = AstMockObjectPreTestPass()
        obj = SipDialogPreTestCondition(TestConfig())
        obj.register_asterisk_instance(ast)
        obj.evaluate()
        self.assertEqual(obj.getStatus(), 'Passed')

    def test_pre_test_fail(self):
        ast = AstMockObjectPreTestFail()
        obj = SipDialogPreTestCondition(TestConfig())
        obj.register_asterisk_instance(ast)
        obj.evaluate()
        self.assertEqual(obj.getStatus(), 'Failed')

    def test_pre_test_fail_multi_asterisk(self):
        ast1 = AstMockObjectPreTestFail()
        ast2 = AstMockObjectPreTestPass()
        obj = SipDialogPreTestCondition(TestConfig())
        obj.register_asterisk_instance(ast1)
        obj.register_asterisk_instance(ast2)
        obj.evaluate()
        self.assertEqual(obj.getStatus(), 'Failed')

    def test_post_test_pass(self):
        ast = AstMockObjectPostTestPass()
        obj = SipDialogPostTestCondition(TestConfigWithHistory())
        obj.register_asterisk_instance(ast)
        obj.evaluate()
        self.assertEqual(obj.getStatus(), 'Passed')

    def test_post_test_no_dialog_pass(self):
        ast = AstMockObjectPostTestNoDialogsPass()
        obj = SipDialogPostTestCondition(TestConfig())
        obj.register_asterisk_instance(ast)
        obj.evaluate()
        self.assertEqual(obj.getStatus(), 'Passed')

    def test_post_test_no_hangup_fail(self):
        ast = AstMockObjectPostTestNoHangupFail()
        logger.debug("Running post_test_no_hangup_fail")
        obj = SipDialogPostTestCondition(TestConfigWithHistory())
        obj.register_asterisk_instance(ast)
        obj.evaluate()
        self.assertEqual(obj.getStatus(), 'Failed')

    def test_post_test_no_destruction_fail(self):
        ast = AstMockObjectPostTestNoDestructionFail()
        obj = SipDialogPostTestCondition(TestConfigWithHistory())
        obj.register_asterisk_instance(ast)
        obj.evaluate()
        self.assertEqual(obj.getStatus(), 'Failed')

    def test_post_test_multi_asterisk_fail(self):
        ast1 = AstMockObjectPostTestNoHangupFail()
        ast2 = AstMockObjectPostTestNoDestructionFail()
        ast3 = AstMockObjectPostTestNoDialogsPass()
        ast4 = AstMockObjectPostTestPass()
        obj = SipDialogPostTestCondition(TestConfigWithHistory())
        obj.register_asterisk_instance(ast1)
        obj.register_asterisk_instance(ast2)
        obj.register_asterisk_instance(ast3)
        obj.register_asterisk_instance(ast4)
        obj.evaluate()
        self.assertEqual(obj.getStatus(), 'Failed')

def main():
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()


if __name__ == "__main__":
    main()
