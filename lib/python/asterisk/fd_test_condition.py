#!/usr/bin/env python
"""Test condition for file descriptors

Copyright (C) 2011-2012, Digium, Inc.
Matt Jordan <mjordan@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
"""

import logging

from twisted.internet import defer
from test_conditions import TestCondition

LOGGER = logging.getLogger(__name__)

class FileDescriptor(object):
    """A small object that tracks a file descriptor.

    The object parses a line from the Asterisk CLI command core show fd to
    populate its values
    """

    def __init__(self, line):
        """Constructor

        Keyword Arguments:
        line A raw line received from Asterisk that describes a FD
        """
        self.number = -1
        self.info = "Unknown"

        line = line.strip()
        tokens = line.partition(' ')
        self.number = int(tokens[0])
        self.info = tokens[2].strip()


class FdTestCondition(TestCondition):
    """Base class for the file descriptor pre- and post-test
    checks. This class provides a common mechanism to get the file
    descriptors from Asterisk and populate them in a dictionary for
    tracking
    """

    def __init__(self, test_config):
        """Constructor

        Keyword Arguments:
        test_config The test config object
        """
        super(FdTestCondition, self).__init__(test_config)
        self.file_descriptors = {}
        # core show fd is dependent on DEBUG_FD_LEAKS
        self.add_build_option("DEBUG_FD_LEAKS", "1")

    def get_file_descriptors(self, ast):
        """Get the file descriptors from some instance of Asterisk"""

        def __show_fd_callback(result):
            """Callback when CLI command has finished"""

            lines = result.output
            if 'No such command' in lines:
                return result
            if 'Unable to connect to remote asterisk' in lines:
                return result

            # Trim off the first and last lines
            lines = lines[lines.find('\n'):].strip()
            lines = lines[:lines.find("Asterisk ending")].strip()
            line_tokens = lines.split('\n')
            fds = []
            for line in line_tokens:
                # chan_sip is going to create sockets for the active channels
                # and won't close them until the dialog is reclaimed - 32
                # seconds after the test.  We ignore the UDP socket file
                # descriptors because of this.
                if 'socket(PF_INET,SOCK_DGRAM,"udp")' in line:
                    LOGGER.debug("Ignoring created UDP socket: " + line)
                    continue
                # If we have MALLOC_DEBUG on and are writing out to the mmlog,
                # ignore
                if '__ast_mm_init' in line:
                    LOGGER.debug("Ignoring malloc debug: " + line)
                    continue
                fd = FileDescriptor(line)
                if fd.number != -1:
                    LOGGER.debug("Tracking %d [%s]", fd.number, fd.info)
                    fds.append(fd)
                else:
                    LOGGER.warn("Failed to parse [%s] into file descriptor "
                                "object" % line)
            self.file_descriptors[result.host] = fds

        return ast.cli_exec("core show fd").addCallback(__show_fd_callback)


class FdPreTestCondition(FdTestCondition):
    """The File Descriptor Pre-TestCondition object"""

    def evaluate(self, related_test_condition=None):
        """Evaluate the test condition"""

        def __raise_finished(finished_deferred):
            """Called when all CLI commands have finished"""
            finished_deferred.callback(self)
            return finished_deferred

        # Automatically pass the pre-test condition - whatever file descriptors
        # are currently open are needed by Asterisk and merely expected to exist
        # when the test is finished
        super(FdPreTestCondition, self).pass_check()

        finished_deferred = defer.Deferred()
        exec_list = [super(FdPreTestCondition, self).get_file_descriptors(ast)
            for ast in self.ast]
        defer.DeferredList(exec_list).addCallback(__raise_finished,
                                                  finished_deferred)

        return finished_deferred


class FdPostTestCondition(FdTestCondition):
    """The File Descriptor Post-TestCondition object"""

    def evaluate(self, related_test_condition=None):
        """Evaluate the test condition"""

        def __file_descriptors_obtained(finished_deferred):
            """Callback when all CLI commands have finished"""
            for ast_host in related_test_condition.file_descriptors.keys():
                if not ast_host in self.file_descriptors:
                    super(FdPostTestCondition, self).fail_check(
                        "Asterisk host in pre-test check [%s]"
                        " not found in post-test check" % ast_host)
                else:
                    # Find all file descriptors in pre-check not in post-check
                    for fd in related_test_condition.file_descriptors[ast_host]:
                        if (len([f for f in self.file_descriptors[ast_host] if fd.number == f.number]) == 0):
                            super(FdPostTestCondition, self).fail_check(
                                "Failed to find file descriptor %d [%s] in "
                                "post-test check" % (fd.number, fd.info))
                    # Find all file descriptors in post-check not in pre-check
                    for fd in self.file_descriptors[ast_host]:
                        if (len([f for f in related_test_condition.file_descriptors[ast_host] if fd.number == f.number]) == 0):
                            super(FdPostTestCondition, self).fail_check(
                                "Failed to find file descriptor %d [%s] in "
                                "pre-test check" % (fd.number, fd.info))
            super(FdPostTestCondition, self).pass_check()
            finished_deferred.callback(self)
            return finished_deferred

        if related_test_condition == None:
            msg = "No pre-test condition object provided"
            super(FdPostTestCondition, self).fail_check(msg)
            return

        finished_deferred = defer.Deferred()
        exec_list = [super(FdPostTestCondition, self).get_file_descriptors(ast)
                     for ast in self.ast]
        defer.DeferredList(exec_list).addCallback(__file_descriptors_obtained,
                                                  finished_deferred)
        return finished_deferred

