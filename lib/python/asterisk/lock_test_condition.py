#!/usr/bin/env python
"""Held locks test condition

Copyright (C) 2011-2012, Digium, Inc.
Matt Jordan <mjordan@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
"""

import logging
import logging.config
import unittest

from twisted.internet import defer
from .test_conditions import TestCondition

LOGGER = logging.getLogger(__name__)


class LockSequence(object):
    """This class represents a sequence of lock objects"""

    def __init__(self):
        """Constructor"""

        self.thread_id = ""
        self.thread_name = ""
        self.thread_line = -1
        self.thread_file = ""
        self.thread_func = ""
        self.locks = []

    def __str__(self):
        ret_string = ("Thread %s[%s] (started at %s::%s[%d])\n" %
                      (self.thread_name, self.thread_id, self.thread_file,
                       self.thread_func, self.thread_line))
        for lock in self.locks:
            ret_string += str(lock)
        return ret_string

    def parse_lock_sequence(self, lock_text):
        """Assume that we get this without the leading stuff and that we have
        just our info. The first and last tokens will not be lock information
        """
        tokens = lock_text.split("=== --->")
        i = 0
        for token in tokens:
            if i != 0:
                obj = LockObject()
                obj.parse_lock_information(token)
                self.locks.append(obj)
            i += 1

        thread_line = tokens[0].strip().lstrip("===\n").lstrip("=== Thread ID: ")
        thread_tokens = thread_line.split(" ")
        i = 0
        for thread_token in thread_tokens:
            if thread_token.strip() != "":
                if i == 0:
                    self.thread_id = thread_token
                elif i == 1:
                    self.thread_name = thread_token.lstrip("(")
                    # 2 and 3 consist of 'started at'
                elif i == 4:
                    thread_line_token = thread_token.lstrip("[").rstrip("]").strip()
                    if thread_line_token != "":
                        self.thread_line = int(thread_line_token)
                    else:
                        # Sometimes the line number will have a leading space,
                        # causing the bracket to be treated as a token. Try
                        # again on the next pass.
                        i -= 1
                elif i == 5:
                    self.thread_file = thread_token
                elif i == 6:
                    self.thread_func = thread_token.rstrip("())")
                i += 1


class LockObject(object):
    """This class represents a detected sequence of locks in the system"""

    def __init__(self):
        """Constructor"""
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
        self.locked_file = ""
        self.locked_line = -1
        self.locked_func = ""

    def __str__(self):
        ret_string = ("%s %s %s(%d): %s at %s::%s[%d] (locked %d times)\n" %
                      ("Held" if self.held else "Waiting for",
                       self.type, self.name, self.id, self.addr, self.file,
                       self.func, self.line_number, self.lock_count))
        for backtrace in self.backtrace:
            ret_string += backtrace + '\n'
        if (self.locked_file != ""):
            ret_string += ("Locked at: %s::%s[%d]\n" %
                           (self.locked_file,
                            self.locked_func,
                            self.locked_line))
        return ret_string

    def parse_lock_information(self, lock_text):
        """Parse out the lock information.  This should be everything
        but the leading === ---> in a lock dump block
        """
        lock_text = lock_text.lstrip("=== --->").strip()
        if "=== --- ---> Locked Here" in lock_text:
            lock_line = lock_text[lock_text.find("=== --- ---> Locked Here"):]
            lock_line = lock_line.lstrip("=== --- ---> Locked Here")
            lock_tokens = lock_line.split(" ")
            self.locked_file = lock_tokens[1]
            # lock_tokens[2] is 'line'
            self.locked_line = int(lock_tokens[3])
            self.locked_func = lock_tokens[4].strip().lstrip("(").rstrip(")")
            lock_text = lock_text[:lock_text.find("=== --- ---> Locked Here")]

        lock_lines = lock_text.partition('\n')
        backtrace_temp = lock_lines[2].split('\n')
        for backtrace in backtrace_temp:
            if backtrace.strip() != "":
                self.backtrace.append(backtrace)

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
    """Class that performs checking of locks during test execution.  Note that
    this class acts as both the pre- and post-test condition check - being
    deadlocked is never a good thing.
    """

    def __init__(self, test_config):
        """Constructor

        Keyword Arguments:
        test_config The TestConfig object for the test
        """
        super(LockTestCondition, self).__init__(test_config)
        self.locks = []

        # core show locks is dependent on DEBUG_THREADS
        self.add_build_option("DEBUG_THREADS", "1")

    def __get_locks(self, ast):
        """Build the locks for an instance of Asterisk

        Returns:
        A deferred for when the locks are built for a given instance
        """
        def __show_locks_callback(result):
            """Callback when 'core show locks' has finished"""
            locks = result.output
            # The first 6 lines are header information - look for a return thread ID
            if "=== Thread ID:" in locks:
                locks = locks[locks.find("=== Thread ID:"):]

                lock_tokens = locks.split("=== -------------------------------------------------------------------")
                for token in lock_tokens:
                    if "Thread ID" in token:
                        try:
                            obj = LockSequence()
                            obj.parse_lock_sequence(token)
                            self.locks.append((result.host, obj))
                        except:
                            msg = ("Unable to parse lock information into a "
                                   "manageable object:\n%s" % token)
                            LOGGER.warning(msg)
            return result

        deferred = ast.cli_exec("core show locks")
        deferred.addCallback(__show_locks_callback)
        return deferred

    def evaluate(self, related_test_condition=None):
        """Evaluate the condition"""

        def __lock_info_obtained(finished_deferred):
            """Callback when lock information has been obtained"""
            if (len(self.locks) > 0):
                #Sometimes, a lock will be held at the end of a test run
                # (typically a logger RDLCK). Only report a held lock as a
                # failure if the thread is waiting for another lock - that would
                # indicate that we may be in a deadlock situation.  Since that
                # shouldnt happen either before or after a test run, treat that
                # as an error.
                for lock_pair in self.locks:
                    LOGGER.info("Detected locks on Asterisk instance: %s" %
                                lock_pair[0])
                    LOGGER.info("Lock trace: %s" % str(lock_pair[1]))
                    for lock in lock_pair[1].locks:
                        if not lock.held:
                            msg = "Lock detected in a waiting state"
                            super(LockTestCondition, self).fail_check(msg)

            if super(LockTestCondition, self).get_status() == 'Inconclusive':
                super(LockTestCondition, self).pass_check()
            finished_deferred.callback(self)
            return finished_deferred

        # Build up the locks for each instance of asterisk
        finished_deferred = defer.Deferred()
        defer.DeferredList([self.__get_locks(ast) for ast in self.ast]
                           ).addCallback(__lock_info_obtained,
                                         finished_deferred)
        return finished_deferred


class AstMockObjectPassed(object):
    """A lock output that passed"""

    def __init__(self):
        """Constructor"""
        self.host = "127.0.0.2"

    def cli_exec(self, command, sync):
        """Fake out a CLI command execution"""
        lock_lines = "=======================================================================\n"
        lock_lines += "=== Currently Held Locks ==============================================\n"
        lock_lines += "=======================================================================\n"
        lock_lines += "===\n"
        lock_lines += "=== <pending> <lock#> (<file>): <lock type> <line num> <function> <lock name> <lock addr> (times locked)\n"
        lock_lines += "===\n"
        lock_lines += "===\n"
        lock_lines += "=======================================================================\n"
        return lock_lines


class AstMockObjectFailure(object):
    """A lock object that failed"""

    def __init__(self):
        """Constructor"""
        self.host = "127.0.0.1"

    def cli_exec(self, command, sync):
        """Fake out a CLI command execution"""
        lock_lines = "=======================================================================\n"
        lock_lines += "=== Currently Held Locks ==============================================\n"
        lock_lines += "=======================================================================\n"
        lock_lines += "===\n"
        lock_lines += "=== <pending> <lock#> (<file>): <lock type> <line num> <function> <lock name> <lock addr> (times locked)\n"
        lock_lines += "===\n"
        lock_lines += "=== Thread ID: 0x402c6940 (do_monitor           started at [25114] chan_sip.c restart_monitor())\n"
        lock_lines += "=== ---> Lock #0 (chan_sip.c): MUTEX 24629 handle_request_do &netlock 0x2aaabe671a40 (1)\n"
        lock_lines += "/usr/local/asterisk-1.8.6.0/sbin/asterisk(ast_bt_get_addresses+0x1a) [0x4e9679]\n"
        lock_lines += "/usr/local/asterisk-1.8.6.0/sbin/asterisk(__ast_pthread_mutex_lock+0xf6) [0x4e22d9]\n"
        lock_lines += "/usr/local/asterisk-1.8.6.0/lib/asterisk/modules/chan_sip.so [0x2aaabe423ee8]\n"
        lock_lines += "=== ---> Lock #1 (chan_sip.c): MUTEX 24629 handle_request_do &netlock 0x2aaabe671a40 (1)\n"
        lock_lines += "=== --- ---> Locked Here: channel.c line 4304 (ast_indicate_data)\n"
        lock_lines += "=== -------------------------------------------------------------------\n"
        lock_lines += "===\n"
        lock_lines += "=== Thread ID: 0x449ec940 (netconsole           started at [ 1351] asterisk.c listener())\n"
        lock_lines += "=== ---> Waiting for Lock #0 (astobj2.c): MUTEX 842 internal_ao2_iterator_next a->c 0x2aaaac491f50 (1)\n"
        lock_lines += "/usr/local/asterisk-1.8.6.0/sbin/asterisk(ast_bt_get_addresses+0x1a) [0x4e9679]\n"
        lock_lines += "/usr/local/asterisk-1.8.6.0/sbin/asterisk(__ast_pthread_mutex_lock+0xf6) [0x4e22d9]\n"
        lock_lines += "/usr/local/asterisk-1.8.6.0/sbin/asterisk(__ao2_lock+0x53) [0x4456fc]\n"
        lock_lines += "/usr/local/asterisk-1.8.6.0/sbin/asterisk [0x446cec]\n"
        lock_lines += "/usr/local/asterisk-1.8.6.0/sbin/asterisk(__ao2_iterator_next+0x29) [0x447134]\n"
        lock_lines += "/usr/local/asterisk-1.8.6.0/sbin/asterisk(ast_channel_iterator_next+0x19) [0x46cf7d]\n"
        lock_lines += "/usr/local/asterisk-1.8.6.0/sbin/asterisk [0x489e43]\n"
        lock_lines += "/usr/local/asterisk-1.8.6.0/sbin/asterisk(ast_cli_command_full+0x222) [0x48eec4]\n"
        lock_lines += "/usr/local/asterisk-1.8.6.0/sbin/asterisk(ast_cli_command_multiple_full+0x92) [0x48f035]\n"
        lock_lines += "/usr/local/asterisk-1.8.6.0/sbin/asterisk [0x43d129]\n"
        lock_lines += "/usr/local/asterisk-1.8.6.0/sbin/asterisk [0x5661c6]\n"
        lock_lines += "/lib64/libpthread.so.0 [0x3d1d80673d]\n"
        lock_lines += "/lib64/libc.so.6(clone+0x6d) [0x3d1ccd44bd]\n"
        lock_lines += "=== --- ---> Locked Here: astobj2.c line 657 (internal_ao2_callback)\n"
        lock_lines += "=== -------------------------------------------------------------------\n"
        lock_lines += "===\n"
        lock_lines += "=== Thread ID: 0x44a68940 (netconsole           started at [ 1351] asterisk.c listener())\n"
        lock_lines += "=== ---> Waiting for Lock #0 (astobj2.c): MUTEX 842 internal_ao2_iterator_next a->c 0x2aaaac491f50 (1)\n"
        lock_lines += "/usr/local/asterisk-1.8.6.0/sbin/asterisk(ast_bt_get_addresses+0x1a) [0x4e9679]\n"
        lock_lines += "/usr/local/asterisk-1.8.6.0/sbin/asterisk(__ast_pthread_mutex_lock+0xf6) [0x4e22d9]\n"
        lock_lines += "/usr/local/asterisk-1.8.6.0/sbin/asterisk(__ao2_lock+0x53) [0x4456fc]\n"
        lock_lines += "/usr/local/asterisk-1.8.6.0/sbin/asterisk [0x446cec]\n"
        lock_lines += "/usr/local/asterisk-1.8.6.0/sbin/asterisk(__ao2_iterator_next+0x29) [0x447134]\n"
        lock_lines += "/usr/local/asterisk-1.8.6.0/sbin/asterisk(ast_channel_iterator_next+0x19) [0x46cf7d]\n"
        lock_lines += "/usr/local/asterisk-1.8.6.0/sbin/asterisk [0x489e43]\n"
        lock_lines += "/usr/local/asterisk-1.8.6.0/sbin/asterisk(ast_cli_command_full+0x222) [0x48eec4]\n"
        lock_lines += "/usr/local/asterisk-1.8.6.0/sbin/asterisk(ast_cli_command_multiple_full+0x92) [0x48f035]\n"
        lock_lines += "/usr/local/asterisk-1.8.6.0/sbin/asterisk [0x43d129]\n"
        lock_lines += "/usr/local/asterisk-1.8.6.0/sbin/asterisk [0x5661c6]\n"
        lock_lines += "/lib64/libpthread.so.0 [0x3d1d80673d]\n"
        lock_lines += "/lib64/libc.so.6(clone+0x6d) [0x3d1ccd44bd]\n"
        lock_lines += "=== --- ---> Locked Here: astobj2.c line 657 (internal_ao2_callback)\n"
        lock_lines += "=== -------------------------------------------------------------------\n"
        lock_lines += "===\n"
        lock_lines += "=======================================================================\n"
        return lock_lines


class TestConfig(object):
    """Fake TestConfig object"""

    def __init__(self):
        """ Values here don't matter much - we just need to have something """
        self.class_type_name = "asterisk.LockTestCondition.LockTestCondition"
        self.pass_expected = True
        self.type = "Post"
        self.related_condition = ""
        self.config = {}


class LockTestConditionUnitTest(unittest.TestCase):
    """Unit tests for LockTestCondition"""

    def test_evaluate_failed(self):
        """Test a failed locking condition"""
        ast = AstMockObjectFailure()
        obj = LockTestCondition(TestConfig())
        obj.register_asterisk_instance(ast)
        obj.evaluate()
        self.assertEqual(obj.get_status(), 'Failed')

    def test_evaluate_pass(self):
        """Test a passed locking condition"""
        ast = AstMockObjectPassed()
        obj = LockTestCondition(TestConfig())
        obj.register_asterisk_instance(ast)
        obj.evaluate()
        self.assertEqual(obj.get_status(), 'Passed')

    def test_evaluate_multiple(self):
        """Test multiple results"""
        ast1 = AstMockObjectPassed()
        ast2 = AstMockObjectFailure()
        obj = LockTestCondition(TestConfig())
        obj.register_asterisk_instance(ast1)
        obj.register_asterisk_instance(ast2)
        obj.evaluate()
        self.assertEqual(obj.get_status(), 'Failed')


class LockSequenceUnitTest(unittest.TestCase):
    """Tests for parsing a lock sequence"""

    def test_single_object_no_held_info(self):
        """Test a lock sequence with no waiting lock"""

        lock_lines = "=== Thread ID: 0x7f668c142700 (do_monitor           started at [25915] chan_sip.c restart_monitor())\n"
        lock_lines += "=== ---> Lock #0 (chan_sip.c): MUTEX 25390 handle_request_do &netlock 0x7f6652193900 (1)\n"
        lock_lines += "main/logger.c:1302 ast_bt_get_addresses() (0x505e53+1D)\n"
        lock_lines += "main/lock.c:193 __ast_pthread_mutex_lock() (0x4fe55c+D9)\n"
        lock_lines += "channels/chan_sip.c:25393 handle_request_do()\n"
        lock_lines += "channels/chan_sip.c:25352 sipsock_read()\n"
        lock_lines += "main/io.c:288 ast_io_wait() (0x4f8228+19C)\n"
        lock_lines += "channels/chan_sip.c:25882 do_monitor()\n"
        lock_lines += "main/utils.c:1010 dummy_start()\n"
        lock_lines += "libpthread.so.0 <unknown>()\n"
        lock_lines += "libc.so.6 clone() (0x31be0e0bc0+6D)\n"

        obj = LockSequence()
        obj.parse_lock_sequence(lock_lines)

    def test_large_multiple_object(self):
        """Test with a waiting lock"""

        lock_lines = "=== Thread ID: 0x449ec940 (netconsole           started at [ 1351] asterisk.c listener())\n"
        lock_lines += "=== ---> Waiting for Lock #0 (astobj2.c): MUTEX 842 internal_ao2_iterator_next a->c 0x2aaaac491f50 (1)\n"
        lock_lines += "/usr/local/asterisk-1.8.6.0/sbin/asterisk(ast_bt_get_addresses+0x1a) [0x4e9679]\n"
        lock_lines += "/usr/local/asterisk-1.8.6.0/sbin/asterisk(__ast_pthread_mutex_lock+0xf6) [0x4e22d9]\n"
        lock_lines += "/usr/local/asterisk-1.8.6.0/sbin/asterisk(__ao2_lock+0x53) [0x4456fc]\n"
        lock_lines += "/usr/local/asterisk-1.8.6.0/sbin/asterisk [0x446cec]\n"
        lock_lines += "/usr/local/asterisk-1.8.6.0/sbin/asterisk(__ao2_iterator_next+0x29) [0x447134]\n"
        lock_lines += "/usr/local/asterisk-1.8.6.0/sbin/asterisk(ast_channel_iterator_next+0x19) [0x46cf7d]\n"
        lock_lines += "/usr/local/asterisk-1.8.6.0/sbin/asterisk [0x489e43]\n"
        lock_lines += "/usr/local/asterisk-1.8.6.0/sbin/asterisk(ast_cli_command_full+0x222) [0x48eec4]\n"
        lock_lines += "/usr/local/asterisk-1.8.6.0/sbin/asterisk(ast_cli_command_multiple_full+0x92) [0x48f035]\n"
        lock_lines += "/usr/local/asterisk-1.8.6.0/sbin/asterisk [0x43d129]\n"
        lock_lines += "/usr/local/asterisk-1.8.6.0/sbin/asterisk [0x5661c6]\n"
        lock_lines += "/lib64/libpthread.so.0 [0x3d1d80673d]\n"
        lock_lines += "/lib64/libc.so.6(clone+0x6d) [0x3d1ccd44bd]\n"
        lock_lines += "=== --- ---> Locked Here: astobj2.c line 657 (internal_ao2_callback)\n"

        obj = LockSequence()
        obj.parse_lock_sequence(lock_lines)
        self.assertEqual(obj.thread_id, "0x449ec940")
        self.assertEqual(obj.thread_name, "netconsole")
        self.assertEqual(obj.thread_line, 1351)
        self.assertEqual(obj.thread_file, "asterisk.c")
        self.assertEqual(obj.thread_func, "listener")
        self.assertTrue(len(obj.locks) == 1)
        self.assertEqual(obj.locks[0].locked_file, "astobj2.c")
        self.assertEqual(obj.locks[0].locked_line, 657)
        self.assertEqual(obj.locks[0].locked_func, "internal_ao2_callback")

    def test_single_object(self):
        """Test a lock held somewhere else"""

        lock_lines = "=== Thread ID: 0x402c6940 (do_monitor           started at [25114] chan_sip.c restart_monitor())\n"
        lock_lines += "=== ---> Lock #0 (chan_sip.c): MUTEX 24629 handle_request_do &netlock 0x2aaabe671a40 (1)\n"
        lock_lines += "/usr/local/asterisk-1.8.6.0/sbin/asterisk(ast_bt_get_addresses+0x1a) [0x4e9679]\n"
        lock_lines += "/usr/local/asterisk-1.8.6.0/sbin/asterisk(__ast_pthread_mutex_lock+0xf6) [0x4e22d9]\n"
        lock_lines += "/usr/local/asterisk-1.8.6.0/lib/asterisk/modules/chan_sip.so [0x2aaabe423ee8]\n"
        lock_lines += "=== --- ---> Locked Here: channel.c line 4304 (ast_indicate_data)\n"

        obj = LockSequence()
        obj.parse_lock_sequence(lock_lines)
        self.assertEqual(obj.thread_id, "0x402c6940")
        self.assertEqual(obj.thread_name, "do_monitor")
        self.assertEqual(obj.thread_line, 25114)
        self.assertEqual(obj.thread_file, "chan_sip.c")
        self.assertEqual(obj.thread_func, "restart_monitor")
        self.assertTrue(len(obj.locks) == 1)
        self.assertEqual(obj.locks[0].locked_file, "channel.c")
        self.assertEqual(obj.locks[0].locked_line, 4304)
        self.assertEqual(obj.locks[0].locked_func, "ast_indicate_data")
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
        """Test multiple locks with no backtrace"""

        lock_lines = "=== Thread ID: 0x402c6940 (do_monitor           started at [25114] chan_sip.c restart_monitor())\n"
        lock_lines += "=== ---> Lock #0 (chan_sip.c): MUTEX 24629 handle_request_do &netlock 0x2aaabe671a40 (1)\n"
        lock_lines += "=== ---> Lock #1 (astobj2.c): MUTEX 657 internal_ao2_callback c 0x2aaaac491f50 (1)\n"
        lock_lines += "=== ---> Waiting for Lock #2 (channel.c): MUTEX 1691 ast_channel_cmp_cb chan 0x2aaaacd3a4e0 (1)\n"
        lock_lines += "=== --- ---> Locked Here: channel.c line 4304 (ast_indicate_data)\n"

        obj = LockSequence()
        obj.parse_lock_sequence(lock_lines)
        self.assertEqual(obj.thread_id, "0x402c6940")
        self.assertEqual(obj.thread_name, "do_monitor")
        self.assertEqual(obj.thread_line, 25114)
        self.assertEqual(obj.thread_file, "chan_sip.c")
        self.assertEqual(obj.thread_func, "restart_monitor")
        self.assertTrue(len(obj.locks) == 3)
        self.assertEqual(obj.locks[2].locked_file, "channel.c")
        self.assertEqual(obj.locks[2].locked_line, 4304)
        self.assertEqual(obj.locks[2].locked_func, "ast_indicate_data")
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
    """Unit tests for LockObject"""

    def test_no_backtrace(self):
        """Test creating a lock object with no thread backtrace"""

        lock_line = "=== ---> Waiting for Lock #0 (sig_ss7.c): MUTEX 636 ss7_linkset &linkset->lock 0x2aaab8a6b588 (1)"
        obj = LockObject()
        obj.parse_lock_information(lock_line)
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
        """Test creating a lock object with a thread backtrace"""

        lock_lines = "=== ---> Lock #1 (astobj2.c): MUTEX 657 internal_ao2_callback c 0x2aaaac491f50 (1)\n"
        lock_lines += "/usr/local/asterisk-1.8.6.0/sbin/asterisk(ast_bt_get_addresses+0x1a) [0x4e9679]\n"
        lock_lines += "/usr/local/asterisk-1.8.6.0/sbin/asterisk(__ast_pthread_mutex_lock+0xf6) [0x4e22d9]\n"
        lock_lines += "/usr/local/asterisk-1.8.6.0/sbin/asterisk(__ao2_lock+0x53) [0x4456fc]\n"
        lock_lines += "/usr/local/asterisk-1.8.6.0/sbin/asterisk [0x4464be]\n"
        lock_lines += "/usr/local/asterisk-1.8.6.0/sbin/asterisk(__ao2_callback+0x59) [0x446a4e]\n"
        lock_lines += "/usr/local/asterisk-1.8.6.0/sbin/asterisk(__ao2_find+0x2b) [0x446ba7]\n"
        lock_lines += "/usr/local/asterisk-1.8.6.0/sbin/asterisk [0x46d3a7]\n"
        lock_lines += "/usr/local/asterisk-1.8.6.0/sbin/asterisk(ast_channel_get_by_name+0x24) [0x46d3e3]\n"
        lock_lines += "/usr/local/asterisk-1.8.6.0/lib/asterisk/modules/func_channel.so [0x2aaabfba2468]\n"
        lock_lines += "/usr/local/asterisk-1.8.6.0/sbin/asterisk(ast_func_write+0x16a) [0x50aacd]\n"
        lock_lines += "/usr/local/asterisk-1.8.6.0/sbin/asterisk(pbx_builtin_setvar_helper+0x10e) [0x51fff4]\n"
        lock_lines += "/usr/local/asterisk-1.8.6.0/lib/asterisk/modules/chan_sip.so [0x2aaabe422d09]\n"
        lock_lines += "/usr/local/asterisk-1.8.6.0/lib/asterisk/modules/chan_sip.so [0x2aaabe4240a0]\n"
        lock_lines += "/usr/local/asterisk-1.8.6.0/lib/asterisk/modules/chan_sip.so [0x2aaabe423cf1]\n"
        lock_lines += "/usr/local/asterisk-1.8.6.0/sbin/asterisk(ast_io_wait+0x1ba) [0x4dc2e4]\n"
        lock_lines += "/usr/local/asterisk-1.8.6.0/lib/asterisk/modules/chan_sip.so [0x2aaabe425722]\n"
        lock_lines += "/usr/local/asterisk-1.8.6.0/sbin/asterisk [0x5661c6]\n"
        lock_lines += "/lib64/libpthread.so.0 [0x3d1d80673d]\n"
        lock_lines += "/lib64/libc.so.6(clone+0x6d) [0x3d1ccd44bd]\n"

        obj = LockObject()
        obj.parse_lock_information(lock_lines)
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
    """Run the unit tests"""

    logging.basicConfig(level=logging.DEBUG)
    unittest.main()


if __name__ == "__main__":
    main()
