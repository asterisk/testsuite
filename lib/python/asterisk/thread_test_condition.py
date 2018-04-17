#!/usr/bin/env python
"""Test condition for Asterisk threads

Copyright (C) 2011-2012, Digium, Inc.
Matt Jordan <mjordan@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
"""

import logging
from test_conditions import TestCondition
from twisted.internet import defer

LOGGER = logging.getLogger(__name__)


class ThreadTestCondition(TestCondition):
    """Base class for the thread pre-/post-test conditions

    This class is a base class for the pre- and post-test condition classes that
    check thread usage in Asterisk.  It provides common functionality for
    parsing out the results of the 'core show threads' Asterisk command
    """

    def __init__(self, test_config):
        """Constructor

        Keyword Arguments:
        test_config The condition test configuration
        """
        super(ThreadTestCondition, self).__init__(test_config)

        # ast_threads is a list of tuples, where the first entry is the host
        # IP of the Asterisk instance, and the second entry is a list of
        # tuples of thread ID and thread name
        self.ast_threads = []

        self.ignored_threads = (test_config.config.get('ignoredThreads') or
                                test_config.config.get('ignored-threads') or
                                [])

        # Core show threads is not available if LOW_MEMORY is turned on
        self.add_build_option("LOW_MEMORY", "0")

    def parse_threads(self, ast, threads):
        """Parse the thread values from the result of the Asterisk command

        Keyword Arguments:
        ast The Asterisk instance to check
        threads The result of 'core show threads'
        """
        ast_host = ast.host
        thread_list = []
        tokens = threads.split('\n')

        for line in tokens:
            if 'threads listed' in line or 'Asterisk ending' in line:
                continue

            # The result of core show threads includes the Asterisk thread ID
            # immediately after the pthread ID.
            initial_partition = initial_partition[2].partition(' ')
            thread_id = initial_partition[0]
            thread_name = initial_partition[2].partition(' ')[0]
            if (thread_id != "" and thread_name != ""
                    and thread_name not in self.ignored_threads):
                LOGGER.debug("Tracking thread %s[%s]" %
                             (thread_name, thread_id))
                thread_list.append((thread_id, thread_name))

        if (len(thread_list) > 0):
            self.ast_threads.append((ast_host, thread_list))


class ThreadPreTestCondition(ThreadTestCondition):
    """The pre-test condition object.

    This merely records the threads in the system prior to test execution.
    """

    def __init__(self, test_config):
        """Constructor"""
        super(ThreadPreTestCondition, self).__init__(test_config)

    def evaluate(self, related_test_condition=None):
        """Override of TestCondition.evaluate"""

        def __show_threads_callback(result, ast):
            """ Callback from core show threads """
            threads = result.output
            self.parse_threads(ast, threads)
            return result

        def __threads_gathered(result, finished_deferred):
            """Check the results once all threads are gathered"""
            if len(self.ast_threads) > 0:
                # All the pre-test cares about is that we saw threads, not what
                # they are
                super(ThreadPreTestCondition, self).pass_check()
            else:
                msg = "No threads found"
                super(ThreadPreTestCondition, self).fail_check(msg)
            finished_deferred.callback(self)
            return result

        finished_deferred = defer.Deferred()
        defer_list = defer.DeferredList([
            ast.cli_exec("core show threads").addCallback(__show_threads_callback, ast)
            for ast in self.ast])
        defer_list.addCallback(__threads_gathered, finished_deferred)
        return finished_deferred


class ThreadPostTestCondition(ThreadTestCondition):
    """The post-test condition object.

    This records the threads in the system after test execution, and compares
    them against the threads recorded by the instance of ThreadPreTestCondition.
    If any threads were in the system prior to test execution and are not in the
    post-test list (and vice versa), a failure is flagged.
    """

    def __init__(self, test_config):
        """Constructor"""
        super(ThreadPostTestCondition, self).__init__(test_config)

    def evaluate(self, related_test_condition=None):
        """Override of TestCondition.evaluate"""

        def __evaluate_thread_obj_in_list(thread_obj, thread_list):
            """Callback that determines if two thread entries are equal"""
            for obj in thread_list:
                # Ignore any remote connections - they may be us
                if (thread_obj[1] == 'netconsole'):
                    return True
                if (thread_obj[0] == obj[0] and thread_obj[1] == obj[1]):
                    return True
            return False

        def __show_threads_callback(result, ast):
            """Callback from core show threads"""
            threads = result.output
            self.parse_threads(ast, threads)
            return result

        def __threads_gathered(result, finished_deferred):
            """Called after all core show threads are finished"""
            if not self.ast_threads:
                # No threads found
                super(ThreadPostTestCondition,
                      self).fail_check("No threads found")
                finished_deferred.callback(self)
                return result

            for ast in self.ast_threads:
                # Make sure that for every instance of Asterisk we check in the
                # post-test, an equivalent instance of Asterisk was checked in
                # the pre-test
                ast_match_found = False
                for pre_ast in related_test_condition.ast_threads:
                    if (ast[0] != pre_ast[0]):
                        continue
                    ast_match_found = True
                    # Create a list of each thread in the post check not in the
                    # pre check and vice versa
                    bad_post_threads = [
                        thread_obj for thread_obj in ast[1]
                        if not __evaluate_thread_obj_in_list(thread_obj, pre_ast[1])]
                    bad_pre_threads = [
                        thread_obj for thread_obj in pre_ast[1]
                        if not __evaluate_thread_obj_in_list(thread_obj, ast[1])]
                    if (bad_post_threads):
                        for thread_obj in bad_post_threads:
                            msg = ("Failed to find thread %s[%s] on Asterisk "
                                   "instance %s in pre-test check" %
                                   (thread_obj[1], thread_obj[0], ast[0]))
                            super(ThreadPostTestCondition, self).fail_check(msg)
                    if (bad_pre_threads):
                        for thread_obj in bad_pre_threads:
                            msg = ("Failed to find thread %s[%s] on Asterisk "
                                   "instance %s in post-test check" %
                                   (thread_obj[1], thread_obj[0], ast[0]))
                            super(ThreadPostTestCondition, self).fail_check(msg)
                    if (len(bad_post_threads) == 0 and len(bad_pre_threads) == 0):
                        super(ThreadPostTestCondition, self).pass_check()
                if not ast_match_found:
                    msg = ("Unable to find Asterisk instance %s in pre-test "
                           "condition check" % ast[0])
                    super(ThreadPostTestCondition, self).fail_check(msg)
            finished_deferred.callback(self)
            return result

        # This must have a related_test_condition value passed in
        if (related_test_condition is None):
            msg = "No pre-test condition provided"
            super(ThreadPostTestCondition, self).fail_check(msg)
            return

        finished_deferred = defer.Deferred()
        defer_list = defer.DeferredList([
            ast.cli_exec("core show threads").addCallback(__show_threads_callback, ast)
            for ast in self.ast])
        defer_list.addCallback(__threads_gathered, finished_deferred)
        return finished_deferred
