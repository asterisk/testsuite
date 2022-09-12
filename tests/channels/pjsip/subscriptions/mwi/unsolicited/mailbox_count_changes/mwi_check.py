#!/usr/bin/env python

import sys
import logging

sys.path.append("lib/python")

from twisted.internet import reactor
from asterisk.scenario_iterator import singleIterator

LOGGER = logging.getLogger(__name__)

mwiscenarios = [
    {'Name': 'alice-is-notified-1.xml', 'port': '5061', 'target': '127.0.0.1'},
    {'Name': 'alice-is-notified-2.xml', 'port': '5061', 'target': '127.0.0.1'},
    {'Name': 'alice-is-notified-3.xml', 'port': '5061', 'target': '127.0.0.1'},
    {'Name': 'alice-is-notified-4.xml', 'port': '5061', 'target': '127.0.0.1'},
    {'Name': 'done'}
]

mwis = [
        {'Action': 'MWIUpdate', 'Mailbox': 'alice', 'NewMessages':'2', 'OldMessages':'0'},
        {'Action': 'MWIUpdate', 'Mailbox': 'alice', 'NewMessages':'1', 'OldMessages':'1'},
        {'Action': 'MWIUpdate', 'Mailbox': 'alice', 'NewMessages':'0', 'OldMessages':'2'},
        {'Action': 'MWIDelete', 'Mailbox': 'alice'},
        {'Action': 'UserEvent', 'UserEvent': 'testComplete'}
]

def start_test(test_object, junk):
    LOGGER.info("Starting mwi_check")
    testrunner = singleIterator(test_object, mwiscenarios, mwis)
    testrunner.run(junk)

def stop_test():
    return

