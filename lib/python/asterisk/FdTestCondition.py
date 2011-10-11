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

class FileDescriptor(object):
    """
    A small object that tracks a file descriptor.  The object parses
    a line from the Asterisk CLI command core show fd to populate
    its values
    """

    def __init__(self, line):
        self.number = -1
        self.info = "Unknown"

        line = line.strip()
        tokens = line.partition(' ')
        self.number = int(tokens[0])
        self.info = tokens[2].strip()


class FdTestCondition(TestCondition):
    """
    Base class for the file descriptor pre- and post-test
    checks.  This class provides a common mechanism to get the file
    descriptors from Asterisk and populate them in a dictionary for
    tracking
    """

    def __init__(self, test_config):
        super(FdTestCondition, self).__init__(test_config)
        self.file_descriptors = {}
        """ core show fd is dependent on DEBUG_FD_LEAKS """
        self.add_build_option("DEBUG_FD_LEAKS", "1")

    def get_file_descriptors(self, ast):
        if ast == None:
            return

        lines = ast.cli_exec("core show fd")
        if 'No such command' in lines:
            return

        """ Trim off the first and last lines """
        lines = lines[lines.find('\n'):].strip()
        lines = lines[:lines.find("Asterisk ending")].strip()
        line_tokens = lines.split('\n')
        fds = []
        for line in line_tokens:
            """
            chan_sip is going to create sockets for the active channels and won't close them until
            the dialog is reclaimed - 32 seconds after the test.  We ignore the UDP socket file
            descriptors because of this.
            """
            if 'socket(PF_INET,SOCK_DGRAM,"udp")' in line:
                logger.debug("Ignoring created UDP socket: " + line)
                continue
            """
            If we have MALLOC_DEBUG on and are writing out to the mmlog, ignore
            """
            if '__ast_mm_init' in line:
                logger.debug("Ignoring malloc debug: " + line)
                continue
            fd = FileDescriptor(line)
            if fd.number != -1:
                logger.debug("Tracking %d [%s]", fd.number, fd.info)
                fds.append(fd)
            else:
                logger.warn("Failed to parse [%s] into file descriptor object" % line)
        self.file_descriptors[ast.host] = fds

class FdPreTestCondition(FdTestCondition):
    def evaluate(self, related_test_condition = None):
        for ast in self.ast:
            super(FdPreTestCondition, self).get_file_descriptors(ast)

        """
        Automatically pass the pre-test condition - whatever file descriptors are currently
        open are needed by Asterisk and merely expected to exist when the test is finished
        """
        super(FdPreTestCondition, self).passCheck()

class FdPostTestCondition(FdTestCondition):
    def evaluate(self, related_test_condition = None):
        if related_test_condition == None:
            super(FdPostTestCondition, self).failCheck("No pre-test condition object provided")
            return

        for ast in self.ast:
            super(FdPostTestCondition, self).get_file_descriptors(ast)

        for ast_host in related_test_condition.file_descriptors.keys():
            if not ast_host in self.file_descriptors:
                super(FdPostTestCondition, self).failCheck("Asterisk host in pre-test check [%s] not found in post-test check" % ast_host)
            else:
                for fd in related_test_condition.file_descriptors[ast_host]:
                    match = [f for f in self.file_descriptors[ast_host] if fd.number == f.number]
                    if (len(match) == 0):
                        super(FdPostTestCondition, self).failCheck("Failed to find file descriptor %d [%s] in post-test check" % (fd.number, fd.info))
                for fd in self.file_descriptors[ast_host]:
                    match = [f for f in related_test_condition.file_descriptors[ast_host] if fd.number == f.number]
                    if (len(match) == 0):
                        super(FdPostTestCondition, self).failCheck("Failed to find file descriptor %d [%s] in pre-test check" % (fd.number, fd.info))
        super(FdPostTestCondition, self).passCheck()
