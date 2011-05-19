#!/usr/bin/env python
'''
Copyright (C) 2010, Digium, Inc.
Paul Belanger <pabelanger@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
'''

import sys
import logging
from optparse import OptionParser
from twisted.internet import reactor
from starpy import manager, fastagi

from asterisk import Asterisk

log = logging.getLogger('TestCase')

class TestCase(object):
    ast = []
    ami = []
    fastagi = []
    reactor_timeout = 30
    passed = False

    def __init__(self, argv):
        """

        Keywork arguments:
        argv --

        """
        # get version info
        parser = OptionParser()
        parser.add_option("-v", "--version", dest="ast_version",
                help="Asterisk version string")
        parser.add_option("-n", dest="test_name",
                help="Test name")
        parser.add_option("--valgrind", action="store_true",
                dest="valgrind", default=False,
                help="Run Asterisk under valgrind.")

        (self.options, args) = parser.parse_args(argv)
        self.options.base = self.options.test_name.lstrip("tests/")

        reactor.callWhenRunning(self.run)

    def create_asterisk(self, count=1):
        """

        Keywork arguments:
        count --

        """
        for c in range(count):
            print "Creating Asterisk instance %d ..." % (c + 1)
            self.ast.append(Asterisk(base=self.options.base))
            self.ast[c].valgrind = self.options.valgrind
            # Copy shared config files
            self.ast[c].install_configs("%s/configs" %
                    (self.options.test_name))
            # Copy test specific config files
            self.ast[c].install_configs("%s/configs/ast%d" %
                    (self.options.test_name, c + 1))

    def create_ami_factory(self, count=1, username="user", secret="mysecret", port=5038):
        """

        Keywork arguments:
        count --
        username --
        secret --
        port --

        """
        for c in range(count):
            host = "127.0.0.%d" % (c + 1)
            self.ami.append(None)
            print "Creating AMIFactory %d ..." % (c + 1)
            self.ami_factory = manager.AMIFactory(username, secret, c)
            self.ami_factory.login(host).addCallbacks(self.ami_connect,
                    self.ami_login_error)

    def create_fastagi_factory(self, count=1):

        for c in range(count):
            host = "127.0.0.%d" % (c + 1)
            self.fastagi.append(None)
            print "Creating FastAGI Factory %d ..." % (c + 1)
            self.fastagi_factory = fastagi.FastAGIFactory(self.fastagi_connect)
            reactor.listenTCP(4573, self.fastagi_factory,
                    self.reactor_timeout, host)

    def start_asterisk(self):
        """

        """
        for index, item in enumerate(self.ast):
            print "Starting Asterisk instance %d ..." % (index + 1)
            self.ast[index].start()

    def stop_asterisk(self):
        """

        """
        for index, item in enumerate(self.ast):
            print "Stopping Asterisk instance %d ..." % (index + 1)
            self.ast[index].stop()

    def stop_reactor(self):
        """

        """
        print "Stopping Reactor ..."
        if reactor.running:
            reactor.stop()

    def run(self):
        """

        """
        reactor.callLater(self.reactor_timeout, self.stop_reactor)

    def ami_login_error(self, ami):
        print "Error logging into AMI"
        self.stop_reactor()

    def ami_connect(self, ami):
        print "AMI Connect instance %s ..." % (ami.id + 1)
        self.ami[ami.id] = ami

