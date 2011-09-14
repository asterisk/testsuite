#!/usr/bin/env python
'''
Copyright (C) 2011, Digium, Inc.
Matt Jordan <mjordan@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
'''

import logging
import logging.config
from TestConditions import TestCondition

logger = logging.getLogger(__name__)

class ThreadTestCondition(TestCondition):
    """
    This class is a base class for the pre- and post-test condition
    classes that check thread usage in Asterisk.  It provides common
    functionality for parsing out the results of the 'core show threads' Asterisk
    command
    """

    def __init__(self, name):
        super(ThreadTestCondition, self).__init__(name)

        """
        astThreads is a list of tuples, where the first entry is the host IP of the
        Asterisk instance, and the second entry is a list of tuples of thread ID and
        thread name
        """
        self.astThreads = []

        """ Core show threads is not available if LOW_MEMORY is turned on """
        self.add_build_option("LOW_MEMORY", "0")

    def parse_threads(self, ast, threads):
        """
        Parse the thread values from the result of the Asterisk command
        """
        astHost = ast.host
        thread_list = []
        tokens = threads.split('\n')

        for line in tokens:
            if not 'threads listed' in line and not 'Asterisk ending' in line:
                """ get the name and thread ID - strip off the cli_exec / pthread ID """
                initialPartition = line.partition(' ')
                initialPartition = initialPartition[2].partition(' ')
                threadId = initialPartition[0]
                threadName = initialPartition[2].partition(' ')[0]
                if threadId != "" and threadName != "":
                    logger.debug("Tracking thread %s[%s]" % (threadName, threadId))
                    thread_list.append((threadId, threadName))

        if (len(thread_list) > 0):
            astThreadList = astHost, thread_list
            self.astThreads.append(astThreadList)


class ThreadPreTestCondition(ThreadTestCondition):
    """
    The pre-test condition object.  This merely records the threads
    in the system prior to test execution.
    """

    def __init__(self):
        super(ThreadPreTestCondition, self).__init__("ThreadPreTestCondition")

    def evaluate(self, related_test_condition = None):
        for ast in self.ast:
            threads = ast.cli_exec("core show threads", True)
            self.parse_threads(ast, threads)

        if len(self.astThreads) > 0:
            """ All the pre-test cares about is that we saw threads, not what they are """
            super(ThreadPreTestCondition, self).passCheck()
        else:
            super(ThreadPreTestCondition, self).failCheck("No threads found")


class ThreadPostTestCondition(ThreadTestCondition):
    """
    The post-test condition object.  This records the threads in the system
    after test execution, and compares them against the threads recorded by the
    instance of ThreadPreTestCondition.  If any threads were in the system prior
    to test execution and are not in the post-test list (and vice versa), a
    failure is flagged.
    """

    def __init__(self):
        super(ThreadPostTestCondition, self).__init__("ThreadPostTestCondition")

    def evaluate(self, related_test_condition = None):

        def evaluateThreadObjInList(threadObj, threadList):
            """ Local callback that determines if two thread entries are equal """
            for obj in threadList:
                if (threadObj[1] == 'netconsole'):
                    """
                    Some AMI connections, even after being disconnected, show up in core show threads.  Ignore
                    netconsole threads for now.
                    """
                    return True
                if (threadObj[0] == obj[0] and threadObj[1] == obj[1]):
                    return True
            return False

        """ This must have a related_test_condition value passed in """
        if (related_test_condition == None):
            super(ThreadPostTestCondition, self).failCheck("No pre-test condition provided")
            return

        for ast in self.ast:
            threads = ast.cli_exec("core show threads", True)
            self.parse_threads(ast, threads)

        if len(self.astThreads) > 0:
            for ast in self.astThreads:
                """
                Make sure that for every instance of Asterisk we check in the post-test,
                an equivalent instance of Asterisk was checked in the pre-test
                """
                astMatchFound = False
                for preAst in related_test_condition.astThreads:
                    if (ast[0] == preAst[0]):
                        astMatchFound = True

                        """ Create a list of each thread in the post check not in the pre check and vice versa """
                        badPostThreads = [threadObj for threadObj in ast[1] if not evaluateThreadObjInList(threadObj, preAst[1])]
                        badPreThreads = [threadObj for threadObj in preAst[1] if not evaluateThreadObjInList(threadObj, ast[1])]

                        if (len(badPostThreads) > 0):
                            for threadObj in badPostThreads:
                                super(ThreadPostTestCondition, self).failCheck("Failed to find thread %s[%s] on Asterisk instance %s in pre-test check" % (threadObj[1],threadObj[0], ast[0]))

                        if (len(badPreThreads) > 0):
                            for threadObj in badPreThreads:
                                super(ThreadPostTestCondition, self).failCheck("Failed to find thread %s[%s] on Asterisk instance %s in post-test check" % (threadObj[1],threadObj[0], ast[0]))

                        if (len(badPostThreads) == 0 and len(badPreThreads) == 0):
                            super(ThreadPostTestCondition, self).passCheck()

                if not astMatchFound:
                    super(ThreadPostTestCondition, self).failCheck("Unable to find Asterisk instance %s in pre-test condition check", ast[0])
        else:
            """ No threads found """
            super(ThreadPostTestCondition, self).failCheck("No threads found")

