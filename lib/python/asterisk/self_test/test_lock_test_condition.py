#!/usr/bin/env python
"""Held locks test condition unit tests

Copyright (C) 2011-2012, Digium, Inc.
Matt Jordan <mjordan@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
"""

from harness_shared import AstMockOutput, ReadTestFile, main
import unittest
from asterisk.lock_test_condition import LockSequence, LockObject, LockTestCondition


class AstMockObjectPassed(AstMockOutput):
    """A lock output that passed"""

    def __init__(self):
        """Constructor"""
        self.host = "127.0.0.2"

    def cli_exec(self, command):
        """Fake out a CLI command execution"""
        return self.MockDeferFile("locks-pass.txt")


class AstMockObjectFailure(AstMockOutput):
    """A lock object that failed"""

    def cli_exec(self, command):
        """Fake out a CLI command execution"""
        return self.MockDeferFile("locks-fail.txt")


class TestConfig(object):
    """Fake TestConfig object"""

    def __init__(self):
        """ Values here don't matter much - we just need to have something """
        self.class_type_name = "asterisk.LockTestCondition.LockTestCondition"
        self.pass_expected = True
        self.type = "Post"
        self.related_condition = ""
        self.config = {}
        self.enabled = True


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

        obj = LockSequence()
        obj.parse_lock_sequence(ReadTestFile("locks-single-object-no-held-info.txt"))

    def test_large_multiple_object(self):
        """Test with a waiting lock"""

        obj = LockSequence()
        obj.parse_lock_sequence(ReadTestFile("locks-large-multiple-object.txt"))
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

        obj = LockSequence()
        obj.parse_lock_sequence(ReadTestFile("locks-single-object.txt"))
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

        obj = LockSequence()
        obj.parse_lock_sequence(ReadTestFile("locks-multiple-objects-no-backtrace.txt"))
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

        lock_line = "=== ---> Waiting for Lock #0 (sig_ss7.c): " + \
                    "MUTEX 636 ss7_linkset &linkset->lock 0x2aaab8a6b588 (1)"
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

        obj = LockObject()
        obj.parse_lock_information(ReadTestFile("locks-backtrace.txt"))
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


if __name__ == "__main__":
    main()
