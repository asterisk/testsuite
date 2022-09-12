#!/usr/bin/env python
"""Pluggable modules for the mwi_aggregate test

Copyright (C) 2014, Digium, Inc.
Mark Michelson <mmichelson@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
"""

import mailbox
import sys
import logging

sys.path.append("lib/python")
from asterisk.scenario_iterator import multiIterator

LOGGER = logging.getLogger(__name__)

mwiscenarios = [
        {'Name': 'mailbox_a', 'sequence': [
                {'Name': 'alice-is-notified-1.xml', 'port': '5061', 'target': '127.0.0.1'},
                {'Name': 'bob-is-notified-1.xml', 'port': '5062', 'target': '127.0.0.1'} ]},
        {'Name': 'mailbox_b', 'sequence': [
                {'Name': 'alice-is-notified-2.xml', 'port': '5061', 'target': '127.0.0.1'},
                {'Name': 'bob-is-notified-2.xml', 'port': '5062', 'target': '127.0.0.1'} ]},
        {'Name': 'done'}
]

mwis = [
        {'Messages': [
                {'Action': 'MWIUpdate', 'Mailbox': 'mailbox_a', 'NewMessages':'2', 'OldMessages':'1'} ]},
        {'Messages': [
                {'Action': 'MWIUpdate', 'Mailbox': 'mailbox_b', 'NewMessages':'3', 'OldMessages':'3'} ]},
        {'Messages': [
                {'Action': 'UserEvent', 'UserEvent': 'testComplete'} ]}
]

def start_test(test_object, junk):
    LOGGER.info("Starting mwi_check")
    testrunner = multiIterator(test_object, mwiscenarios, mwis)
    testrunner.run(junk)

def stop_test():
    return

