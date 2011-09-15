#!/usr/bin/env python
'''
Copyright (C) 2011, Digium, Inc.
Matt Jordan <mjordan@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
'''

import logging
import logging.config
import unittest

from TestConditions import TestCondition

logger = logging.getLogger(__name__)

class LockSequence(object):
    """
    This class represents a sequence of lock objects
    """
    def __init__(self):
        self.threadId = ""
        self.threadName = ""
        self.threadLine = -1
        self.threadFile = ""
        self.threadFunc = ""
        self.locks = []

    def __str__(self):
        retString = "Thread %s[%s] (started at %s::%s[%d])\n" % (self.threadName,
            self.threadId, self.threadFile, self.threadFunc, self.threadLine)
        for l in self.locks:
            retString += str(l)
        return retString

    def parseLockSequence(self, lock_text):
        """
        Assume that we get this without the leading stuff and that we have just our info.  The
        first and last tokens will not be lock information
        """
        tokens = lock_text.split("=== --->")
        i = 0
        for token in tokens:
            if i != 0:
                obj = LockObject()
                obj.parseLockInformation(token)
                self.locks.append(obj)
            i += 1

        threadLine = tokens[0].strip().lstrip("===\n").lstrip("=== Thread ID: ")
        threadTokens = threadLine.split(" ")
        i = 0
        for threadToken in threadTokens:
            if threadToken.strip() != "":
                if i == 0:
                    self.threadId = threadToken
                elif i == 1:
                    self.threadName = threadToken.lstrip("(")
                    """ 2 and 3 consist of 'started at'"""
                elif i == 4:
                    threadLineToken = threadToken.lstrip("[").rstrip("]").strip()
                    if threadLineToken != "":
                        self.threadLine = int(threadLineToken)
                    else:
                        """Sometimes the line number will have a leading space, causing the bracket to be treated as
                        a token.  Try again on the next pass."""
                        i -= 1
                elif i == 5:
                    self.threadFile = threadToken
                elif i == 6:
                    self.threadFunc = threadToken.rstrip("())")
                i += 1

class LockObject(object):
    """
    This class represents a detected sequence of locks in the system
    """

    def __init__(self):
        self.id = -1
        self.type = "UNKNOWN"
        self.file = ""
        self.line_number = -1
        self.func = ""
        self.name = ""
        self.addr = ""
        self.lock_count = -1
        self.held = True
        self.backtrace = []
        self.lockedFile = ""
        self.lockedLine = -1
        self.lockedFunc = ""

    def __str__(self):
        retString = "%s %s %s(%d): %s at %s::%s[%d] (locked %d times)\n" % ("Held" if self.held else "Waiting for",
            self.type, self.name, self.id, self.addr, self.file, self.func, self.line_number, self.lock_count)
        for b in self.backtrace:
            retString += b + '\n'
        if (self.lockedFile != ""):
            retString += "Locked at: %s::%s[%d]\n" % (self.lockedFile, self.lockedFunc, self.lockedLine)
        return retString

    def parseLockInformation(self, lock_text):
        """
        Parse out the lock information.  This should be everything
        but the leading === ---> in a lock dump block
        """
        lock_text = lock_text.lstrip("=== --->").strip()
        if "=== --- ---> Locked Here" in lock_text:
            lockLine = lock_text[lock_text.find("=== --- ---> Locked Here"):]
            lockLine = lockLine.lstrip("=== --- ---> Locked Here")
            lockTokens = lockLine.split(" ")
            self.lockedFile = lockTokens[1]
            """ lockTokens[2] is 'line' """
            self.lockedLine = int(lockTokens[3])
            self.lockedFunc = lockTokens[4].strip().lstrip("(").rstrip(")")
            lock_text = lock_text[:lock_text.find("=== --- ---> Locked Here")]

        lock_lines = lock_text.partition('\n')
        backtrace_temp = lock_lines[2].split('\n')
        for bt in backtrace_temp:
            if bt.strip() != "":
                self.backtrace.append(bt)

        lock_info = lock_lines[0]
        if "Waiting for" in lock_info:
            self.held = False
            lock_info = lock_info.lstrip("Waiting for")
        lock_info = lock_info.lstrip("Lock").strip()
        lock_tokens = lock_info.split(' ')
        self.id = int(lock_tokens[0].lstrip("#"))
        self.file = lock_tokens[1].lstrip("(").rstrip("):")
        self.type = lock_tokens[2]
        self.line_number = int(lock_tokens[3])
        self.func = lock_tokens[4]
        self.name = lock_tokens[5]
        self.addr = lock_tokens[6]
        self.lock_count = int(lock_tokens[7].lstrip("(").rstrip(")"))

class LockTestCondition(TestCondition):
    """
    Class that performs checking of locks during test execution.  Note that
    this class acts as both the pre- and post-test condition check - being deadlocked
    is never a good thing.
    """

    def __init__(self, test_config):
        super(LockTestCondition, self).__init__(test_config)
        self.locks = []

        """ core show locks is dependent on DEBUG_THREADS """
        self.add_build_option("DEBUG_THREADS", "1")

    def __get_locks(self, ast):
        locks = ast.cli_exec("core show locks", True)
        """ The first 6 lines are header information - look for a return thread ID """
        if "=== Thread ID:" in locks:
            locks = locks[locks.find("=== Thread ID:"):]
            lockTokens = locks.split("=== -------------------------------------------------------------------")
            for token in lockTokens:
                if "Thread ID" in token:
                    try:
                        obj = LockSequence()
                        obj.parseLockSequence(token)
                        t = ast.host, obj
                        self.locks.append(t)
                    except:
                        logger.warning("Unable to parse lock information into a manageable object:\n%s" % token)

    def evaluate(self, related_test_condition = None):
        """ Build up the locks for each instance of asterisk """
        for ast in self.ast:
            self.__get_locks(ast)

        if (len(self.locks) > 0):
            """
            Sometimes, a lock will be held at the end of a test run (typically a logger RDLCK).  Only
            report a held lock as a failure if the thread is waiting for another lock - that would
            indicate that we may be in a deadlock situation.  Since that shouldnt happen either
            before or after a test run, treat that as an error.
            """
            for lockPair in self.locks:
                logger.info("Detected locks on Asterisk instance: %s" % lockPair[0])
                logger.info("Lock trace: %s" % str(lockPair[1]))
                for lock in lockPair[1].locks:
                    if not lock.held:
                        super(LockTestCondition, self).failCheck("Lock detected in a waiting state")

        if super(LockTestCondition, self).getStatus() == 'Inconclusive':
            super(LockTestCondition, self).passCheck()


class AstMockObjectPassed(object):
    def __init__(self):
        self.host = "127.0.0.2"

    def cli_exec(self, command, sync):
        lockLines = "=======================================================================\n"
        lockLines += "=== Currently Held Locks ==============================================\n"
        lockLines += "=======================================================================\n"
        lockLines += "===\n"
        lockLines += "=== <pending> <lock#> (<file>): <lock type> <line num> <function> <lock name> <lock addr> (times locked)\n"
        lockLines += "===\n"
        lockLines += "===\n"
        lockLines += "=======================================================================\n"
        return lockLines

class AstMockObjectFailure(object):
    def __init__(self):
        self.host = "127.0.0.1"

    def cli_exec(self, command, sync):
        lockLines = "=======================================================================\n"
        lockLines += "=== Currently Held Locks ==============================================\n"
        lockLines += "=======================================================================\n"
        lockLines += "===\n"
        lockLines += "=== <pending> <lock#> (<file>): <lock type> <line num> <function> <lock name> <lock addr> (times locked)\n"
        lockLines += "===\n"
        lockLines += "=== Thread ID: 0x402c6940 (do_monitor           started at [25114] chan_sip.c restart_monitor())\n"
        lockLines += "=== ---> Lock #0 (chan_sip.c): MUTEX 24629 handle_request_do &netlock 0x2aaabe671a40 (1)\n"
        lockLines += "/usr/local/asterisk-1.8.6.0/sbin/asterisk(ast_bt_get_addresses+0x1a) [0x4e9679]\n"
        lockLines += "/usr/local/asterisk-1.8.6.0/sbin/asterisk(__ast_pthread_mutex_lock+0xf6) [0x4e22d9]\n"
        lockLines += "/usr/local/asterisk-1.8.6.0/lib/asterisk/modules/chan_sip.so [0x2aaabe423ee8]\n"
        lockLines += "=== ---> Lock #1 (chan_sip.c): MUTEX 24629 handle_request_do &netlock 0x2aaabe671a40 (1)\n"
        lockLines += "=== --- ---> Locked Here: channel.c line 4304 (ast_indicate_data)\n"
        lockLines += "=== -------------------------------------------------------------------\n"
        lockLines += "===\n"
        lockLines += "=== Thread ID: 0x449ec940 (netconsole           started at [ 1351] asterisk.c listener())\n"
        lockLines += "=== ---> Waiting for Lock #0 (astobj2.c): MUTEX 842 internal_ao2_iterator_next a->c 0x2aaaac491f50 (1)\n"
        lockLines += "/usr/local/asterisk-1.8.6.0/sbin/asterisk(ast_bt_get_addresses+0x1a) [0x4e9679]\n"
        lockLines += "/usr/local/asterisk-1.8.6.0/sbin/asterisk(__ast_pthread_mutex_lock+0xf6) [0x4e22d9]\n"
        lockLines += "/usr/local/asterisk-1.8.6.0/sbin/asterisk(__ao2_lock+0x53) [0x4456fc]\n"
        lockLines += "/usr/local/asterisk-1.8.6.0/sbin/asterisk [0x446cec]\n"
        lockLines += "/usr/local/asterisk-1.8.6.0/sbin/asterisk(__ao2_iterator_next+0x29) [0x447134]\n"
        lockLines += "/usr/local/asterisk-1.8.6.0/sbin/asterisk(ast_channel_iterator_next+0x19) [0x46cf7d]\n"
        lockLines += "/usr/local/asterisk-1.8.6.0/sbin/asterisk [0x489e43]\n"
        lockLines += "/usr/local/asterisk-1.8.6.0/sbin/asterisk(ast_cli_command_full+0x222) [0x48eec4]\n"
        lockLines += "/usr/local/asterisk-1.8.6.0/sbin/asterisk(ast_cli_command_multiple_full+0x92) [0x48f035]\n"
        lockLines += "/usr/local/asterisk-1.8.6.0/sbin/asterisk [0x43d129]\n"
        lockLines += "/usr/local/asterisk-1.8.6.0/sbin/asterisk [0x5661c6]\n"
        lockLines += "/lib64/libpthread.so.0 [0x3d1d80673d]\n"
        lockLines += "/lib64/libc.so.6(clone+0x6d) [0x3d1ccd44bd]\n"
        lockLines += "=== --- ---> Locked Here: astobj2.c line 657 (internal_ao2_callback)\n"
        lockLines += "=== -------------------------------------------------------------------\n"
        lockLines += "===\n"
        lockLines += "=== Thread ID: 0x44a68940 (netconsole           started at [ 1351] asterisk.c listener())\n"
        lockLines += "=== ---> Waiting for Lock #0 (astobj2.c): MUTEX 842 internal_ao2_iterator_next a->c 0x2aaaac491f50 (1)\n"
        lockLines += "/usr/local/asterisk-1.8.6.0/sbin/asterisk(ast_bt_get_addresses+0x1a) [0x4e9679]\n"
        lockLines += "/usr/local/asterisk-1.8.6.0/sbin/asterisk(__ast_pthread_mutex_lock+0xf6) [0x4e22d9]\n"
        lockLines += "/usr/local/asterisk-1.8.6.0/sbin/asterisk(__ao2_lock+0x53) [0x4456fc]\n"
        lockLines += "/usr/local/asterisk-1.8.6.0/sbin/asterisk [0x446cec]\n"
        lockLines += "/usr/local/asterisk-1.8.6.0/sbin/asterisk(__ao2_iterator_next+0x29) [0x447134]\n"
        lockLines += "/usr/local/asterisk-1.8.6.0/sbin/asterisk(ast_channel_iterator_next+0x19) [0x46cf7d]\n"
        lockLines += "/usr/local/asterisk-1.8.6.0/sbin/asterisk [0x489e43]\n"
        lockLines += "/usr/local/asterisk-1.8.6.0/sbin/asterisk(ast_cli_command_full+0x222) [0x48eec4]\n"
        lockLines += "/usr/local/asterisk-1.8.6.0/sbin/asterisk(ast_cli_command_multiple_full+0x92) [0x48f035]\n"
        lockLines += "/usr/local/asterisk-1.8.6.0/sbin/asterisk [0x43d129]\n"
        lockLines += "/usr/local/asterisk-1.8.6.0/sbin/asterisk [0x5661c6]\n"
        lockLines += "/lib64/libpthread.so.0 [0x3d1d80673d]\n"
        lockLines += "/lib64/libc.so.6(clone+0x6d) [0x3d1ccd44bd]\n"
        lockLines += "=== --- ---> Locked Here: astobj2.c line 657 (internal_ao2_callback)\n"
        lockLines += "=== -------------------------------------------------------------------\n"
        lockLines += "===\n"
        lockLines += "=======================================================================\n"
        return lockLines

class TestConfig(object):
    def __init__(self):
        """ Values here don't matter much - we just need to have something """
        self.classTypeName = "asterisk.LockTestCondition.LockTestCondition"
        self.passExpected = True
        self.type = "Post"
        self.relatedCondition = ""
        self.config = {}

class LockTestConditionUnitTest(unittest.TestCase):
    def test_evaluate_failed(self):
        ast = AstMockObjectFailure()
        obj = LockTestCondition(TestConfig())
        obj.register_asterisk_instance(ast)
        obj.evaluate()
        self.assertEqual(obj.getStatus(), 'Failed')

    def test_evaluate_pass(self):
        ast = AstMockObjectPassed()
        obj = LockTestCondition(TestConfig())
        obj.register_asterisk_instance(ast)
        obj.evaluate()
        self.assertEqual(obj.getStatus(), 'Passed')

    def test_evaluate_multiple(self):
        ast1 = AstMockObjectPassed()
        ast2 = AstMockObjectFailure()
        obj = LockTestCondition(TestConfig())
        obj.register_asterisk_instance(ast1)
        obj.register_asterisk_instance(ast2)
        obj.evaluate()
        self.assertEqual(obj.getStatus(), 'Failed')

class LockSequenceUnitTest(unittest.TestCase):
    def test_single_object_no_held_info(self):
        lockLines = "=== Thread ID: 0x7f668c142700 (do_monitor           started at [25915] chan_sip.c restart_monitor())\n"
        lockLines += "=== ---> Lock #0 (chan_sip.c): MUTEX 25390 handle_request_do &netlock 0x7f6652193900 (1)\n"
        lockLines += "main/logger.c:1302 ast_bt_get_addresses() (0x505e53+1D)\n"
        lockLines += "main/lock.c:193 __ast_pthread_mutex_lock() (0x4fe55c+D9)\n"
        lockLines += "channels/chan_sip.c:25393 handle_request_do()\n"
        lockLines += "channels/chan_sip.c:25352 sipsock_read()\n"
        lockLines += "main/io.c:288 ast_io_wait() (0x4f8228+19C)\n"
        lockLines += "channels/chan_sip.c:25882 do_monitor()\n"
        lockLines += "main/utils.c:1010 dummy_start()\n"
        lockLines += "libpthread.so.0 <unknown>()\n"
        lockLines += "libc.so.6 clone() (0x31be0e0bc0+6D)\n"

        obj = LockSequence()
        obj.parseLockSequence(lockLines)

    def test_large_multiple_object(self):
        lockLines = "=== Thread ID: 0x449ec940 (netconsole           started at [ 1351] asterisk.c listener())\n"
        lockLines += "=== ---> Waiting for Lock #0 (astobj2.c): MUTEX 842 internal_ao2_iterator_next a->c 0x2aaaac491f50 (1)\n"
        lockLines += "/usr/local/asterisk-1.8.6.0/sbin/asterisk(ast_bt_get_addresses+0x1a) [0x4e9679]\n"
        lockLines += "/usr/local/asterisk-1.8.6.0/sbin/asterisk(__ast_pthread_mutex_lock+0xf6) [0x4e22d9]\n"
        lockLines += "/usr/local/asterisk-1.8.6.0/sbin/asterisk(__ao2_lock+0x53) [0x4456fc]\n"
        lockLines += "/usr/local/asterisk-1.8.6.0/sbin/asterisk [0x446cec]\n"
        lockLines += "/usr/local/asterisk-1.8.6.0/sbin/asterisk(__ao2_iterator_next+0x29) [0x447134]\n"
        lockLines += "/usr/local/asterisk-1.8.6.0/sbin/asterisk(ast_channel_iterator_next+0x19) [0x46cf7d]\n"
        lockLines += "/usr/local/asterisk-1.8.6.0/sbin/asterisk [0x489e43]\n"
        lockLines += "/usr/local/asterisk-1.8.6.0/sbin/asterisk(ast_cli_command_full+0x222) [0x48eec4]\n"
        lockLines += "/usr/local/asterisk-1.8.6.0/sbin/asterisk(ast_cli_command_multiple_full+0x92) [0x48f035]\n"
        lockLines += "/usr/local/asterisk-1.8.6.0/sbin/asterisk [0x43d129]\n"
        lockLines += "/usr/local/asterisk-1.8.6.0/sbin/asterisk [0x5661c6]\n"
        lockLines += "/lib64/libpthread.so.0 [0x3d1d80673d]\n"
        lockLines += "/lib64/libc.so.6(clone+0x6d) [0x3d1ccd44bd]\n"
        lockLines += "=== --- ---> Locked Here: astobj2.c line 657 (internal_ao2_callback)\n"

        obj = LockSequence()
        obj.parseLockSequence(lockLines)
        self.assertEqual(obj.threadId, "0x449ec940")
        self.assertEqual(obj.threadName, "netconsole")
        self.assertEqual(obj.threadLine, 1351)
        self.assertEqual(obj.threadFile, "asterisk.c")
        self.assertEqual(obj.threadFunc, "listener")
        self.assertTrue(len(obj.locks) == 1)
        self.assertEqual(obj.locks[0].lockedFile, "astobj2.c")
        self.assertEqual(obj.locks[0].lockedLine, 657)
        self.assertEqual(obj.locks[0].lockedFunc, "internal_ao2_callback")

    def test_single_object(self):
        lockLines = "=== Thread ID: 0x402c6940 (do_monitor           started at [25114] chan_sip.c restart_monitor())\n"
        lockLines += "=== ---> Lock #0 (chan_sip.c): MUTEX 24629 handle_request_do &netlock 0x2aaabe671a40 (1)\n"
        lockLines += "/usr/local/asterisk-1.8.6.0/sbin/asterisk(ast_bt_get_addresses+0x1a) [0x4e9679]\n"
        lockLines += "/usr/local/asterisk-1.8.6.0/sbin/asterisk(__ast_pthread_mutex_lock+0xf6) [0x4e22d9]\n"
        lockLines += "/usr/local/asterisk-1.8.6.0/lib/asterisk/modules/chan_sip.so [0x2aaabe423ee8]\n"
        lockLines += "=== --- ---> Locked Here: channel.c line 4304 (ast_indicate_data)\n"

        obj = LockSequence()
        obj.parseLockSequence(lockLines)
        self.assertEqual(obj.threadId, "0x402c6940")
        self.assertEqual(obj.threadName, "do_monitor")
        self.assertEqual(obj.threadLine, 25114)
        self.assertEqual(obj.threadFile, "chan_sip.c")
        self.assertEqual(obj.threadFunc, "restart_monitor")
        self.assertTrue(len(obj.locks) == 1)
        self.assertEqual(obj.locks[0].lockedFile, "channel.c")
        self.assertEqual(obj.locks[0].lockedLine, 4304)
        self.assertEqual(obj.locks[0].lockedFunc, "ast_indicate_data")
        self.assertEqual(obj.locks[0].id, 0)
        self.assertEqual(obj.locks[0].type, "MUTEX")
        self.assertEqual(obj.locks[0].file, "chan_sip.c")
        self.assertEqual(obj.locks[0].line_number, 24629)
        self.assertEqual(obj.locks[0].func, "handle_request_do")
        self.assertEqual(obj.locks[0].name, "&netlock")
        self.assertEqual(obj.locks[0].addr, "0x2aaabe671a40")
        self.assertEqual(obj.locks[0].lock_count, 1)
        self.assertTrue(obj.locks[0].held)
        self.assertTrue(len(obj.locks[0].backtrace) == 3)

    def test_multiple_objects_no_backtrace(self):
        lockLines = "=== Thread ID: 0x402c6940 (do_monitor           started at [25114] chan_sip.c restart_monitor())\n"
        lockLines += "=== ---> Lock #0 (chan_sip.c): MUTEX 24629 handle_request_do &netlock 0x2aaabe671a40 (1)\n"
        lockLines += "=== ---> Lock #1 (astobj2.c): MUTEX 657 internal_ao2_callback c 0x2aaaac491f50 (1)\n"
        lockLines += "=== ---> Waiting for Lock #2 (channel.c): MUTEX 1691 ast_channel_cmp_cb chan 0x2aaaacd3a4e0 (1)\n"
        lockLines += "=== --- ---> Locked Here: channel.c line 4304 (ast_indicate_data)\n"

        obj = LockSequence()
        obj.parseLockSequence(lockLines)
        self.assertEqual(obj.threadId, "0x402c6940")
        self.assertEqual(obj.threadName, "do_monitor")
        self.assertEqual(obj.threadLine, 25114)
        self.assertEqual(obj.threadFile, "chan_sip.c")
        self.assertEqual(obj.threadFunc, "restart_monitor")
        self.assertTrue(len(obj.locks) == 3)
        self.assertEqual(obj.locks[2].lockedFile, "channel.c")
        self.assertEqual(obj.locks[2].lockedLine, 4304)
        self.assertEqual(obj.locks[2].lockedFunc, "ast_indicate_data")
        self.assertEqual(obj.locks[0].id, 0)
        self.assertEqual(obj.locks[0].type, "MUTEX")
        self.assertEqual(obj.locks[0].file, "chan_sip.c")
        self.assertEqual(obj.locks[0].line_number, 24629)
        self.assertEqual(obj.locks[0].func, "handle_request_do")
        self.assertEqual(obj.locks[0].name, "&netlock")
        self.assertEqual(obj.locks[0].addr, "0x2aaabe671a40")
        self.assertEqual(obj.locks[0].lock_count, 1)
        self.assertTrue(obj.locks[0].held)
        self.assertTrue(len(obj.locks[0].backtrace) == 0)

class LockObjectUnitTest(unittest.TestCase):
    def test_no_backtrace(self):
        lockLine = "=== ---> Waiting for Lock #0 (sig_ss7.c): MUTEX 636 ss7_linkset &linkset->lock 0x2aaab8a6b588 (1)"
        obj = LockObject()
        obj.parseLockInformation(lockLine)
        self.assertEqual(obj.id, 0)
        self.assertEqual(obj.type, "MUTEX")
        self.assertEqual(obj.file, "sig_ss7.c")
        self.assertEqual(obj.line_number, 636)
        self.assertEqual(obj.func, "ss7_linkset")
        self.assertEqual(obj.name, "&linkset->lock")
        self.assertEqual(obj.addr, "0x2aaab8a6b588")
        self.assertEqual(obj.lock_count, 1)
        self.assertFalse(obj.held)
        self.assertTrue(len(obj.backtrace) == 0)

    def test_with_backtrace(self):
        lockLines = "=== ---> Lock #1 (astobj2.c): MUTEX 657 internal_ao2_callback c 0x2aaaac491f50 (1)\n"
        lockLines += "/usr/local/asterisk-1.8.6.0/sbin/asterisk(ast_bt_get_addresses+0x1a) [0x4e9679]\n"
        lockLines += "/usr/local/asterisk-1.8.6.0/sbin/asterisk(__ast_pthread_mutex_lock+0xf6) [0x4e22d9]\n"
        lockLines += "/usr/local/asterisk-1.8.6.0/sbin/asterisk(__ao2_lock+0x53) [0x4456fc]\n"
        lockLines += "/usr/local/asterisk-1.8.6.0/sbin/asterisk [0x4464be]\n"
        lockLines += "/usr/local/asterisk-1.8.6.0/sbin/asterisk(__ao2_callback+0x59) [0x446a4e]\n"
        lockLines += "/usr/local/asterisk-1.8.6.0/sbin/asterisk(__ao2_find+0x2b) [0x446ba7]\n"
        lockLines += "/usr/local/asterisk-1.8.6.0/sbin/asterisk [0x46d3a7]\n"
        lockLines += "/usr/local/asterisk-1.8.6.0/sbin/asterisk(ast_channel_get_by_name+0x24) [0x46d3e3]\n"
        lockLines += "/usr/local/asterisk-1.8.6.0/lib/asterisk/modules/func_channel.so [0x2aaabfba2468]\n"
        lockLines += "/usr/local/asterisk-1.8.6.0/sbin/asterisk(ast_func_write+0x16a) [0x50aacd]\n"
        lockLines += "/usr/local/asterisk-1.8.6.0/sbin/asterisk(pbx_builtin_setvar_helper+0x10e) [0x51fff4]\n"
        lockLines += "/usr/local/asterisk-1.8.6.0/lib/asterisk/modules/chan_sip.so [0x2aaabe422d09]\n"
        lockLines += "/usr/local/asterisk-1.8.6.0/lib/asterisk/modules/chan_sip.so [0x2aaabe4240a0]\n"
        lockLines += "/usr/local/asterisk-1.8.6.0/lib/asterisk/modules/chan_sip.so [0x2aaabe423cf1]\n"
        lockLines += "/usr/local/asterisk-1.8.6.0/sbin/asterisk(ast_io_wait+0x1ba) [0x4dc2e4]\n"
        lockLines += "/usr/local/asterisk-1.8.6.0/lib/asterisk/modules/chan_sip.so [0x2aaabe425722]\n"
        lockLines += "/usr/local/asterisk-1.8.6.0/sbin/asterisk [0x5661c6]\n"
        lockLines += "/lib64/libpthread.so.0 [0x3d1d80673d]\n"
        lockLines += "/lib64/libc.so.6(clone+0x6d) [0x3d1ccd44bd]\n"

        obj = LockObject()
        obj.parseLockInformation(lockLines)
        self.assertEqual(obj.id, 1)
        self.assertEqual(obj.type, "MUTEX")
        self.assertEqual(obj.file, "astobj2.c")
        self.assertEqual(obj.line_number, 657)
        self.assertEqual(obj.func, "internal_ao2_callback")
        self.assertEqual(obj.name, "c")
        self.assertEqual(obj.addr, "0x2aaaac491f50")
        self.assertEqual(obj.lock_count, 1)
        self.assertTrue(obj.held)
        self.assertTrue(len(obj.backtrace) == 19)


def main():
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()


if __name__ == "__main__":
    main()
