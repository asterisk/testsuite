#!/usr/bin/env python

import sys
import logging

sys.path.append("lib/python")

from twisted.internet import reactor

LOGGER = logging.getLogger(__name__)

states = [
    ('INUSE', 2, "Offline"),
    ('ONHOLD', 2, "Offline"),
    ('BUSY', 2, "Offline"),
    ('RINGING', 2, "Offline"),
    ('UNAVAILABLE', 2, "Offline"),
    ('NOT_INUSE', 1, "Online"),
    ('', 1, "Online")  # Final state upon subscription teardown
]

# Walk the device states, scheduling each one second apart.
def walk_states(test_object, extra):
    test_ami = test_object.ami[0]
    statedelay = 0
    for state in states:
        statedelay += 1
        reactor.callLater(statedelay, test_ami.setVar, channel="",
                                   variable="DEVICE_STATE(Custom:bob)",
                                   value=state[0])
