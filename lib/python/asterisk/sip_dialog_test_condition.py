#!/usr/bin/env python
"""Test condition for verifying SIP dialogs

Copyright (C) 2011-2012, Digium, Inc.
Matt Jordan <mjordan@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
"""

import logging
import logging.config
import unittest

from test_conditions import TestCondition
from twisted.internet import defer

LOGGER = logging.getLogger(__name__)

class SipDialogTestCondition(TestCondition):
    """This class is a base class for the pre- and post-test condition
    classes that check for the existence of SIP dialogs in Asterisk. It provides
    common functionality for parsing out the results of the 'sip show objects'
    and 'sip show history' Asterisk commands
    """

    def __init__(self, test_config):
        """Constructor"""
        super(SipDialogTestCondition, self).__init__(test_config)
        # a dictionary of ast objects to a dictionary of SIP dialogs and a list
        # of their history
        self.dialogs_history = {}
        self._finished_deferred = None
        self.ast = None

    def _get_dialog_names(self, objects):
        """Get the names of dialogs"""
        in_objects = False
        object_list = objects.split('\n')
        dialog_names = []
        for obj in object_list:
            if "Dialog objects" in obj:
                in_objects = True
            if "name:" in obj and in_objects:
                dialog_names.append(obj[obj.find(":") + 1:].strip())
        return dialog_names

    def get_sip_dialogs(self, ast):
        """Build the dialog history and objects for a particular Asterisk
        instance
        """
        def __show_objects_callback(result):
            """Callback for sip show objects"""
            LOGGER.debug(result.output)
            dialog_names = self._get_dialog_names(result.output)
            LOGGER.debug(dialog_names)
            if not dialog_names:
                LOGGER.debug("No SIP history found for Asterisk instance %s" %
                             ast.host)
                self._finished_deferred.callback(ast)
                return result

            deferreds = []
            for name in dialog_names:
                LOGGER.debug("Retrieving history for SIP dialog %s" % name)
                deferred = ast.cli_exec("sip show history %s" % name)
                deferred.addCallback(__show_history_callback)
                deferreds.append(deferred)
            defer.DeferredList(deferreds).addCallback(__history_complete)
            return result

        def __show_history_callback(result):
            """Callback for sip show history"""
            # Get the Call ID from the result
            call_id = result.cli_cmd.replace("sip show history", "").strip()
            raw_history = result.output
            LOGGER.debug(result.output)
            if 'No such SIP Call ID' not in raw_history:
                # dialog got disposed before we could get its history; ignore
                lines = raw_history.split('\n')
                self.dialogs_history[self.ast.host][call_id] = lines
            return result

        def __history_complete(result):
            """Callback when all SIP history has been gathered"""
            self._finished_deferred.callback(ast)
            return result

        self.dialogs_history[ast.host] = {}
        self._finished_deferred = defer.Deferred()
        ast.cli_exec("sip show objects").addCallback(__show_objects_callback)

        return self._finished_deferred


class SipDialogPreTestCondition(SipDialogTestCondition):
    """Check the pre-test conditions for SIP dialogs. This test simply
    checks that there are no SIP dialogs present before test execution.
    """

    def __init__(self, test_config):
        """Constructor"""
        super(SipDialogPreTestCondition, self).__init__(test_config)
        self._counter = 0
        self._finished_deferred = None

    def evaluate(self, related_test_condition=None):
        """Evaluate the condition"""

        def __history_finished(result):
            """Called when the CLI command to get the dialog history finishes"""
            for ast in self.ast:
                if ast.host == result.host:
                    __get_dialogs(ast)
                    return result
            LOGGER.warning("Unable to determine Asterisk instance from CLI " \
                           "command run on host %s" % result.host)
            return result

        def __get_dialogs(ast):
            """Get the dialogs from this asterisk instance"""
            deferd = super(SipDialogPreTestCondition, self).get_sip_dialogs(ast)
            deferd.addCallback(__dialogs_obtained)

        def __dialogs_obtained(result):
            """Called when the dialogs have been populated"""
            dialog_history = self.dialogs_history[result.host]
            if len(dialog_history) > 0:
                # If any dialogs are present before test execution, something
                # funny is going on
                super(SipDialogPreTestCondition, self).fail_check("%d dialogs " \
                    "were detected in Asterisk %s before test execution" %
                    (len(dialog_history), result.host))
            else:
                super(SipDialogPreTestCondition, self).pass_check()
            self._counter += 1
            if self._counter == len(self.ast):
                # All asterisk instances have been checked
                self._finished_deferred.callback(self)
            return result

        self._counter = 0
        self._finished_deferred = defer.Deferred()
        # Turn on history and check for dialogs
        for ast in self.ast:
            ast.cli_exec("sip set history on").addCallback(__history_finished) 
        return self._finished_deferred

class SipDialogPostTestCondition(SipDialogTestCondition):
    """Check the post-test conditions for SIP dialogs.

    This test looks for any SIP dialogs still in existence. If it does not
    detect any, the test passes. If it does detect dialogs, it checks to make
    sure that the dialogs have been hungup and are scheduled for destruction.
    If those two conditions are met, the test passes; otherwise it fails.

    Note: as a future enhancement, implement an AMI command that will force
    garbage collection on the SIP dialogs.  We can then also check that the
    scheduler properly collects SIP dialogs as part of this test.
    """

    def __init__(self, test_config):
        """Constructor"""
        super(SipDialogPostTestCondition, self).__init__(test_config)

        self._counter = 0
        self._finished_deferred = None
        self.history_sequence = []
        if 'history_requirements' in test_config.config:
            self.history_sequence = test_config.config['history_requirements']

    def evaluate(self, related_test_condition=None):
        """Evaluate the condition"""

        def __get_dialogs():
            """Get the dialogs from this asterisk instance"""
            self._counter += 1
            if self._counter == len(self.ast):
                self._finished_deferred.callback(self)
                return
            super(SipDialogPostTestCondition, self).get_sip_dialogs(
                self.ast[self._counter]).addCallback(__dialogs_obtained)

        def __dialogs_obtained(result):
            """Called when the dialogs have been populated"""
            history_requirements = {}
            dialogs_history = self.dialogs_history[self.ast[self._counter].host]
            if not dialogs_history:
                __get_dialogs()
                return result

            # Set up the history statements to look for in each dialog history
            for dialog_name in dialogs_history.keys():
                history_check = {}
                for h_seq in self.history_sequence:
                    history_check[h_seq] = False
                history_requirements[dialog_name] = history_check

            # Assume we pass the check.  This will be overriden if any history
            # check fails
            super(SipDialogPostTestCondition, self).pass_check()
            for dialog, history in dialogs_history.items():
                scheduled = False
                for h_seq in history:
                    if "SchedDestroy" in h_seq:
                        scheduled = True
                    for req in history_requirements[dialog].keys():
                        if req in h_seq:
                            history_requirements[dialog][req] = True
                if not scheduled:
                    super(SipDialogPostTestCondition, self).fail_check(
                        "Dialog %s in Asterisk instance %s not scheduled for " \
                        "destruction" % (dialog, self.ast[self._counter].host))
                for req in history_requirements[dialog].keys():
                    if history_requirements[dialog][req] == False:
                        super(SipDialogPostTestCondition, self).fail_check(
                            "Dialog %s in Asterisk instance %s did not have " \
                            "required step in history: %s" % (dialog,
                                self.ast[self._counter].host, req))
            __get_dialogs()
            return result

        self._finished_deferred = defer.Deferred()
        self._counter = -1
        __get_dialogs()
        return self._finished_deferred

class TestConfig(object):
    """Mock TestConfig object"""

    def __init__(self):
        """Constructor

        Values here don't matter much - we just need to have something"""
        self.type_name = ("asterisk.sip_dialog_test_condition." +
                          "SipDialogPostTestCondition")
        self.pass_expected = True
        self.type = "Post"
        self.related_condition = ""
        self.config = {}

class TestConfigWithHistory(TestConfig):
    """Mock TestConfig object with history requirements"""

    def __init__(self):
        """Constructor"""
        super(TestConfigWithHistory, self).__init__()

        self.config['history_requirements'] = []
        self.config['history_requirements'].append('Hangup')
        self.config['history_requirements'].append('NewChan')

class AstMockObjectPostTestNoDestructionFail(object):
    """Mock out CLI execution from Asterisk instance

    This mock object makes it appear as if a dialog failed to be destroyed
    """
    def __init__(self):
        """Constructor"""
        self.host = "127.0.0.6"

    def cli_exec(self, command):
        """Mock CLI execution/response"""

        ret_string = ""
        if command == "sip show objects":
            ret_string = "-= Peer objects: 4 static, 0 realtime, 0 autocreate =-\n\n"
            ret_string += "name: audio\ntype: peer\nobjflags: 0\nrefcount: 3\n\n"
            ret_string += "name: 7002\ntype: peer\nobjflags: 0\nrefcount: 3\n\n"
            ret_string += "name: 7001\ntype: peer\nobjflags: 0\nrefcount: 1\n\n"
            ret_string += "name: zoiper_01\ntype: peer\nobjflags: 0\nrefcount: 3\n\n"
            ret_string += "-= Peer objects by IP =-\n\n"
            ret_string += "name: zoiper_01\ntype: peer\nobjflags: 0\nrefcount: 3\n\n"
            ret_string += "name: audio\ntype: peer\nobjflags: 0\nrefcount: 3\n\n"
            ret_string += "name: 7002\ntype: peer\nobjflags: 0\nrefcount: 3\n\n"
            ret_string += "-= Registry objects: 0 =-\n\n"
            ret_string += "-= Dialog objects:\n\n"
            ret_string += "name: 2ec048aa4ed1239664f6408f0c5044c4@127.0.0.2:5060\n"
            ret_string += "type: dialog\n"
            ret_string += "objflags: 0\n"
            ret_string += "refcount: 2\n\n"
            ret_string += "name: 2ec048aa4ed1239664f6408f0c5044c5@127.0.0.2:5060\n"
            ret_string += "type: dialog\n"
            ret_string += "objflags: 0\n"
            ret_string += "refcount: 2\n\n"
        elif command == "sip show history 2ec048aa4ed1239664f6408f0c5044c4@127.0.0.2:5060":
            ret_string = "* SIP Call\n"
            ret_string += "1. NewChan         Channel SIP/ast1-00000002 - from 2ec048aa4ed1239664f6408f0c5044\n"
            ret_string += "2. TxReqRel        INVITE / 102 INVITE - INVITE\n"
            ret_string += "3. Rx              SIP/2.0 / 102 INVITE / 100 Trying\n"
            ret_string += "4. Rx              SIP/2.0 / 102 INVITE / 200 OK\n"
            ret_string += "5. TxReq           ACK / 102 ACK - ACK\n"
            ret_string += "6. Rx              BYE / 102 BYE / sip:ast2@127.0.0.2:5060\n"
            ret_string += "7. RTCPaudio       Quality:ssrc=28249381;themssrc=485141946;lp=0;rxjitter=0.000029\n"
            ret_string += "8. RTCPaudioJitter Quality:minrxjitter=0.000000;maxrxjitter=0.000000;avgrxjitter=0\n"
            ret_string += "9. RTCPaudioLoss   Quality:minrxlost=0.000000;maxrxlost=0.000000;avgrxlost=0.00000\n"
            ret_string += "10. RTCPaudioRTT    Quality:minrtt=0.000000;maxrtt=0.000000;avgrtt=0.000000;stdevrt\n"
            ret_string += "11. SchedDestroy    32000 ms\n"
            ret_string += "12. TxResp          SIP/2.0 / 102 BYE - 200 OK\n"
            ret_string += "13. Hangup          Cause Normal Clearing\n"
        elif command == "sip show history 2ec048aa4ed1239664f6408f0c5044c5@127.0.0.2:5060":
            ret_string = "* SIP Call\n"
            ret_string += "1. NewChan         Channel SIP/ast1-00000002 - from 2ec048aa4ed1239664f6408f0c5044\n"
            ret_string += "2. TxReqRel        INVITE / 102 INVITE - INVITE\n"
            ret_string += "3. Rx              SIP/2.0 / 102 INVITE / 100 Trying\n"
            ret_string += "4. Rx              SIP/2.0 / 102 INVITE / 200 OK\n"
            ret_string += "5. TxReq           ACK / 102 ACK - ACK\n"
            ret_string += "6. Rx              BYE / 102 BYE / sip:ast2@127.0.0.2:5060\n"
            ret_string += "7. RTCPaudio       Quality:ssrc=28249381;themssrc=485141946;lp=0;rxjitter=0.000029\n"
            ret_string += "8. RTCPaudioJitter Quality:minrxjitter=0.000000;maxrxjitter=0.000000;avgrxjitter=0\n"
            ret_string += "9. RTCPaudioLoss   Quality:minrxlost=0.000000;maxrxlost=0.000000;avgrxlost=0.00000\n"
            ret_string += "10. RTCPaudioRTT    Quality:minrtt=0.000000;maxrtt=0.000000;avgrtt=0.000000;stdevrt\n"
            ret_string += "11. TxResp          SIP/2.0 / 102 BYE - 200 OK\n"
            ret_string += "12. Hangup          Cause Normal Clearing\n"
        return ret_string

class AstMockObjectPostTestNoHangupFail(object):
    """Mock out CLI execution from Asterisk instance

    This mock object makes it appear as if a channel failed to hangup
    """

    def __init__(self):
        """Constructor"""
        self.host = "127.0.0.5"

    def cli_exec(self, command):
        """Mock CLI execution/response"""

        ret_string = ""
        if command == "sip show objects":
            ret_string = "-= Peer objects: 4 static, 0 realtime, 0 autocreate =-\n\n"
            ret_string += "name: audio\ntype: peer\nobjflags: 0\nrefcount: 3\n\n"
            ret_string += "name: 7002\ntype: peer\nobjflags: 0\nrefcount: 3\n\n"
            ret_string += "name: 7001\ntype: peer\nobjflags: 0\nrefcount: 1\n\n"
            ret_string += "name: zoiper_01\ntype: peer\nobjflags: 0\nrefcount: 3\n\n"
            ret_string += "-= Peer objects by IP =-\n\n"
            ret_string += "name: zoiper_01\ntype: peer\nobjflags: 0\nrefcount: 3\n\n"
            ret_string += "name: audio\ntype: peer\nobjflags: 0\nrefcount: 3\n\n"
            ret_string += "name: 7002\ntype: peer\nobjflags: 0\nrefcount: 3\n\n"
            ret_string += "-= Registry objects: 0 =-\n\n"
            ret_string += "-= Dialog objects:\n\n"
            ret_string += "name: 2ec048aa4ed1239664f6408f0c5044c4@127.0.0.2:5060\n"
            ret_string += "type: dialog\n"
            ret_string += "objflags: 0\n"
            ret_string += "refcount: 2\n\n"
            ret_string += "name: 2ec048aa4ed1239664f6408f0c5044c5@127.0.0.2:5060\n"
            ret_string += "type: dialog\n"
            ret_string += "objflags: 0\n"
            ret_string += "refcount: 2\n\n"
        elif command == "sip show history 2ec048aa4ed1239664f6408f0c5044c4@127.0.0.2:5060":
            ret_string = "* SIP Call\n"
            ret_string += "1. NewChan         Channel SIP/ast1-00000002 - from 2ec048aa4ed1239664f6408f0c5044\n"
            ret_string += "2. TxReqRel        INVITE / 102 INVITE - INVITE\n"
            ret_string += "3. Rx              SIP/2.0 / 102 INVITE / 100 Trying\n"
            ret_string += "4. Rx              SIP/2.0 / 102 INVITE / 200 OK\n"
            ret_string += "5. TxReq           ACK / 102 ACK - ACK\n"
            ret_string += "6. Rx              BYE / 102 BYE / sip:ast2@127.0.0.2:5060\n"
            ret_string += "7. RTCPaudio       Quality:ssrc=28249381;themssrc=485141946;lp=0;rxjitter=0.000029\n"
            ret_string += "8. RTCPaudioJitter Quality:minrxjitter=0.000000;maxrxjitter=0.000000;avgrxjitter=0\n"
            ret_string += "9. RTCPaudioLoss   Quality:minrxlost=0.000000;maxrxlost=0.000000;avgrxlost=0.00000\n"
            ret_string += "10. RTCPaudioRTT    Quality:minrtt=0.000000;maxrtt=0.000000;avgrtt=0.000000;stdevrt\n"
            ret_string += "11. SchedDestroy    32000 ms\n"
            ret_string += "12. TxResp          SIP/2.0 / 102 BYE - 200 OK\n"
        elif command == "sip show history 2ec048aa4ed1239664f6408f0c5044c5@127.0.0.2:5060":
            ret_string = "* SIP Call\n"
            ret_string += "1. NewChan         Channel SIP/ast1-00000002 - from 2ec048aa4ed1239664f6408f0c5044\n"
            ret_string += "2. TxReqRel        INVITE / 102 INVITE - INVITE\n"
            ret_string += "3. Rx              SIP/2.0 / 102 INVITE / 100 Trying\n"
            ret_string += "4. Rx              SIP/2.0 / 102 INVITE / 200 OK\n"
            ret_string += "5. TxReq           ACK / 102 ACK - ACK\n"
            ret_string += "6. Rx              BYE / 102 BYE / sip:ast2@127.0.0.2:5060\n"
            ret_string += "7. RTCPaudio       Quality:ssrc=28249381;themssrc=485141946;lp=0;rxjitter=0.000029\n"
            ret_string += "8. RTCPaudioJitter Quality:minrxjitter=0.000000;maxrxjitter=0.000000;avgrxjitter=0\n"
            ret_string += "9. RTCPaudioLoss   Quality:minrxlost=0.000000;maxrxlost=0.000000;avgrxlost=0.00000\n"
            ret_string += "10. RTCPaudioRTT    Quality:minrtt=0.000000;maxrtt=0.000000;avgrtt=0.000000;stdevrt\n"
            ret_string += "11. SchedDestroy    32000 ms\n"
            ret_string += "12. TxResp          SIP/2.0 / 102 BYE - 200 OK\n"
            ret_string += "13. Hangup          Cause Normal Clearing\n"
        return ret_string

class AstMockObjectPostTestNoDialogsPass(object):
    """Mock out CLI execution from Asterisk instance

    This mock object makes it appear as if there were no dialogs, which is okay
    """
    def __init__(self):
        """Constructor"""
        self.host = "127.0.0.4"

    def cli_exec(self, command):
        """Mock CLI execution/response"""

        ret_string = ""
        if command == "sip show objects":
            ret_string = "-= Peer objects: 4 static, 0 realtime, 0 autocreate =-\n\n"
            ret_string += "name: audio\ntype: peer\nobjflags: 0\nrefcount: 3\n\n"
            ret_string += "name: 7002\ntype: peer\nobjflags: 0\nrefcount: 3\n\n"
            ret_string += "name: 7001\ntype: peer\nobjflags: 0\nrefcount: 1\n\n"
            ret_string += "name: zoiper_01\ntype: peer\nobjflags: 0\nrefcount: 3\n\n"
            ret_string += "-= Peer objects by IP =-\n\n"
            ret_string += "name: zoiper_01\ntype: peer\nobjflags: 0\nrefcount: 3\n\n"
            ret_string += "name: audio\ntype: peer\nobjflags: 0\nrefcount: 3\n\n"
            ret_string += "name: 7002\ntype: peer\nobjflags: 0\nrefcount: 3\n\n"
            ret_string += "-= Registry objects: 0 =-\n\n"
            ret_string += "-= Dialog objects:\n\n"

        return ret_string

class AstMockObjectPostTestPass(object):
    """Mock out CLI execution from Asterisk instance

    This mock object provides two dialogs with acceptable history
    """
    def __init__(self):
        """Constructor"""
        self.host = "127.0.0.3"

    def cli_exec(self, command):
        """Mock CLI execution/response"""

        ret_string = ""
        if command == "sip show objects":
            ret_string = "-= Peer objects: 4 static, 0 realtime, 0 autocreate =-\n\n"
            ret_string += "name: audio\ntype: peer\nobjflags: 0\nrefcount: 3\n\n"
            ret_string += "name: 7002\ntype: peer\nobjflags: 0\nrefcount: 3\n\n"
            ret_string += "name: 7001\ntype: peer\nobjflags: 0\nrefcount: 1\n\n"
            ret_string += "name: zoiper_01\ntype: peer\nobjflags: 0\nrefcount: 3\n\n"
            ret_string += "-= Peer objects by IP =-\n\n"
            ret_string += "name: zoiper_01\ntype: peer\nobjflags: 0\nrefcount: 3\n\n"
            ret_string += "name: audio\ntype: peer\nobjflags: 0\nrefcount: 3\n\n"
            ret_string += "name: 7002\ntype: peer\nobjflags: 0\nrefcount: 3\n\n"
            ret_string += "-= Registry objects: 0 =-\n\n"
            ret_string += "-= Dialog objects:\n\n"
            ret_string += "name: 2ec048aa4ed1239664f6408f0c5044c4@127.0.0.2:5060\n"
            ret_string += "type: dialog\n"
            ret_string += "objflags: 0\n"
            ret_string += "refcount: 2\n\n"
            ret_string += "name: 2ec048aa4ed1239664f6408f0c5044c5@127.0.0.2:5060\n"
            ret_string += "type: dialog\n"
            ret_string += "objflags: 0\n"
            ret_string += "refcount: 2\n\n"
        elif command == "sip show history 2ec048aa4ed1239664f6408f0c5044c4@127.0.0.2:5060":
            ret_string = "* SIP Call\n"
            ret_string += "1. NewChan         Channel SIP/ast1-00000002 - from 2ec048aa4ed1239664f6408f0c5044\n"
            ret_string += "2. TxReqRel        INVITE / 102 INVITE - INVITE\n"
            ret_string += "3. Rx              SIP/2.0 / 102 INVITE / 100 Trying\n"
            ret_string += "4. Rx              SIP/2.0 / 102 INVITE / 200 OK\n"
            ret_string += "5. TxReq           ACK / 102 ACK - ACK\n"
            ret_string += "6. Rx              BYE / 102 BYE / sip:ast2@127.0.0.2:5060\n"
            ret_string += "7. RTCPaudio       Quality:ssrc=28249381;themssrc=485141946;lp=0;rxjitter=0.000029\n"
            ret_string += "8. RTCPaudioJitter Quality:minrxjitter=0.000000;maxrxjitter=0.000000;avgrxjitter=0\n"
            ret_string += "9. RTCPaudioLoss   Quality:minrxlost=0.000000;maxrxlost=0.000000;avgrxlost=0.00000\n"
            ret_string += "10. RTCPaudioRTT    Quality:minrtt=0.000000;maxrtt=0.000000;avgrtt=0.000000;stdevrt\n"
            ret_string += "11. SchedDestroy    32000 ms\n"
            ret_string += "12. TxResp          SIP/2.0 / 102 BYE - 200 OK\n"
            ret_string += "13. Hangup          Cause Normal Clearing\n"
        elif command == "sip show history 2ec048aa4ed1239664f6408f0c5044c5@127.0.0.2:5060":
            ret_string = "* SIP Call\n"
            ret_string += "1. NewChan         Channel SIP/ast1-00000002 - from 2ec048aa4ed1239664f6408f0c5044\n"
            ret_string += "2. TxReqRel        INVITE / 102 INVITE - INVITE\n"
            ret_string += "3. Rx              SIP/2.0 / 102 INVITE / 100 Trying\n"
            ret_string += "4. Rx              SIP/2.0 / 102 INVITE / 200 OK\n"
            ret_string += "5. TxReq           ACK / 102 ACK - ACK\n"
            ret_string += "6. Rx              BYE / 102 BYE / sip:ast2@127.0.0.2:5060\n"
            ret_string += "7. RTCPaudio       Quality:ssrc=28249381;themssrc=485141946;lp=0;rxjitter=0.000029\n"
            ret_string += "8. RTCPaudioJitter Quality:minrxjitter=0.000000;maxrxjitter=0.000000;avgrxjitter=0\n"
            ret_string += "9. RTCPaudioLoss   Quality:minrxlost=0.000000;maxrxlost=0.000000;avgrxlost=0.00000\n"
            ret_string += "10. RTCPaudioRTT    Quality:minrtt=0.000000;maxrtt=0.000000;avgrtt=0.000000;stdevrt\n"
            ret_string += "11. SchedDestroy    32000 ms\n"
            ret_string += "12. TxResp          SIP/2.0 / 102 BYE - 200 OK\n"
            ret_string += "13. Hangup          Cause Normal Clearing\n"
        return ret_string

class AstMockObjectPreTestFail(object):
    """Mock out CLI execution from Asterisk instance

    This mock object provides history during a pre-test call, which is wrong
    """
    def __init__(self):
        """Constructor"""
        self.host = "127.0.0.2"

    def cli_exec(self, command):
        """Mock CLI execution/response"""

        ret_string = ""
        if command == "sip show objects":
            ret_string = "-= Peer objects: 4 static, 0 realtime, 0 autocreate =-\n\n"
            ret_string += "name: audio\ntype: peer\nobjflags: 0\nrefcount: 3\n\n"
            ret_string += "name: 7002\ntype: peer\nobjflags: 0\nrefcount: 3\n\n"
            ret_string += "name: 7001\ntype: peer\nobjflags: 0\nrefcount: 1\n\n"
            ret_string += "name: zoiper_01\ntype: peer\nobjflags: 0\nrefcount: 3\n\n"
            ret_string += "-= Peer objects by IP =-\n\n"
            ret_string += "name: zoiper_01\ntype: peer\nobjflags: 0\nrefcount: 3\n\n"
            ret_string += "name: audio\ntype: peer\nobjflags: 0\nrefcount: 3\n\n"
            ret_string += "name: 7002\ntype: peer\nobjflags: 0\nrefcount: 3\n\n"
            ret_string += "-= Registry objects: 0 =-\n\n"
            ret_string += "-= Dialog objects:\n\n"
            ret_string += "name: 2ec048aa4ed1239664f6408f0c5044c4@127.0.0.2:5060\n"
            ret_string += "type: dialog\n"
            ret_string += "objflags: 0\n"
            ret_string += "refcount: 2\n\n"
        elif command == "sip show history 2ec048aa4ed1239664f6408f0c5044c4@127.0.0.2:5060":
            ret_string = "* SIP Call\n"
            ret_string += "1. NewChan         Channel SIP/ast1-00000002 - from 2ec048aa4ed1239664f6408f0c5044\n"
            ret_string += "2. TxReqRel        INVITE / 102 INVITE - INVITE\n"
            ret_string += "3. Rx              SIP/2.0 / 102 INVITE / 100 Trying\n"
            ret_string += "4. Rx              SIP/2.0 / 102 INVITE / 200 OK\n"
            ret_string += "5. TxReq           ACK / 102 ACK - ACK\n"
            ret_string += "6. Rx              BYE / 102 BYE / sip:ast2@127.0.0.2:5060\n"
            ret_string += "7. RTCPaudio       Quality:ssrc=28249381;themssrc=485141946;lp=0;rxjitter=0.000029\n"
            ret_string += "8. RTCPaudioJitter Quality:minrxjitter=0.000000;maxrxjitter=0.000000;avgrxjitter=0\n"
            ret_string += "9. RTCPaudioLoss   Quality:minrxlost=0.000000;maxrxlost=0.000000;avgrxlost=0.00000\n"
            ret_string += "10. RTCPaudioRTT    Quality:minrtt=0.000000;maxrtt=0.000000;avgrtt=0.000000;stdevrt\n"
            ret_string += "11. SchedDestroy    32000 ms\n"
            ret_string += "12. TxResp          SIP/2.0 / 102 BYE - 200 OK\n"
            ret_string += "13. Hangup          Cause Normal Clearing\n"
        return ret_string

class AstMockObjectPreTestPass(object):
    """Mock out CLI execution from Asterisk instance

    This mock object provides no history during a pre-test call, which is the
    expected state
    """
    def __init__(self):
        """Constructor"""
        self.host = "127.0.0.1"

    def cli_exec(self, command):
        """Mock CLI execution/response"""

        ret_string = ""
        if command == "sip show objects":
            ret_string = "-= Peer objects: 4 static, 0 realtime, 0 autocreate =-\n\n"
            ret_string += "name: audio\ntype: peer\nobjflags: 0\nrefcount: 3\n\n"
            ret_string += "name: 7002\ntype: peer\nobjflags: 0\nrefcount: 3\n\n"
            ret_string += "name: 7001\ntype: peer\nobjflags: 0\nrefcount: 1\n\n"
            ret_string += "name: zoiper_01\ntype: peer\nobjflags: 0\nrefcount: 3\n\n"
            ret_string += "-= Peer objects by IP =-\n\n"
            ret_string += "name: zoiper_01\ntype: peer\nobjflags: 0\nrefcount: 3\n\n"
            ret_string += "name: audio\ntype: peer\nobjflags: 0\nrefcount: 3\n\n"
            ret_string += "name: 7002\ntype: peer\nobjflags: 0\nrefcount: 3\n\n"
            ret_string += "-= Registry objects: 0 =-\n\n"
            ret_string += "-= Dialog objects:\n"
        elif command == "sip show history":
            return "\n"
        return ret_string


class SipDialogTestConditionUnitTest(unittest.TestCase):
    """Unit tests for SipDialogTestCondition objects"""

    def test_pre_test_pass(self):
        """Verify that acceptable pre-test output passes"""
        ast = AstMockObjectPreTestPass()
        obj = SipDialogPreTestCondition(TestConfig())
        obj.register_asterisk_instance(ast)
        obj.evaluate()
        self.assertEqual(obj.get_status(), 'Passed')

    def test_pre_test_fail(self):
        """Verify that unacceptable pre-test output fails"""
        ast = AstMockObjectPreTestFail()
        obj = SipDialogPreTestCondition(TestConfig())
        obj.register_asterisk_instance(ast)
        obj.evaluate()
        self.assertEqual(obj.get_status(), 'Failed')

    def test_pre_test_fail_multi_asterisk(self):
        """Verify that pre-test output from multiple sources fails when one
        of those sources is bad"""
        ast1 = AstMockObjectPreTestFail()
        ast2 = AstMockObjectPreTestPass()
        obj = SipDialogPreTestCondition(TestConfig())
        obj.register_asterisk_instance(ast1)
        obj.register_asterisk_instance(ast2)
        obj.evaluate()
        self.assertEqual(obj.get_status(), 'Failed')

    def test_post_test_pass(self):
        """Verify nominal post-test output"""
        ast = AstMockObjectPostTestPass()
        obj = SipDialogPostTestCondition(TestConfigWithHistory())
        obj.register_asterisk_instance(ast)
        obj.evaluate()
        self.assertEqual(obj.get_status(), 'Passed')

    def test_post_test_no_dialog_pass(self):
        """Verify nominal post-test output with no dialogs passes"""
        ast = AstMockObjectPostTestNoDialogsPass()
        obj = SipDialogPostTestCondition(TestConfig())
        obj.register_asterisk_instance(ast)
        obj.evaluate()
        self.assertEqual(obj.get_status(), 'Passed')

    def test_post_test_no_hangup_fail(self):
        """Verify no hangup detection is caught and results in a failure"""
        ast = AstMockObjectPostTestNoHangupFail()
        obj = SipDialogPostTestCondition(TestConfigWithHistory())
        obj.register_asterisk_instance(ast)
        obj.evaluate()
        self.assertEqual(obj.get_status(), 'Failed')

    def test_post_test_no_destruction_fail(self):
        """Verify no destruction is caught and results in a failure"""
        ast = AstMockObjectPostTestNoDestructionFail()
        obj = SipDialogPostTestCondition(TestConfigWithHistory())
        obj.register_asterisk_instance(ast)
        obj.evaluate()
        self.assertEqual(obj.get_status(), 'Failed')

    def test_post_test_multi_asterisk_fail(self):
        """Test multiple instances of Asterisk where a single failure causes
        a failure in the overall result"""
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
        self.assertEqual(obj.get_status(), 'Failed')

def main():
    """Execute the unit tests"""
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()


if __name__ == "__main__":
    main()
