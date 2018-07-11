"""Held locks test condition

Copyright (C) 2011-2012, Digium, Inc.
Matt Jordan <mjordan@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
"""

import logging
import logging.config

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

        def __lock_info_obtained(lst, finished_deferred):
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

