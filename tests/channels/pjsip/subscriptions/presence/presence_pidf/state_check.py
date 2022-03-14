#!/usr/bin/env python

import sys
import logging

sys.path.append("lib/python")

from twisted.internet import reactor

LOGGER = logging.getLogger(__name__)

states = [
    ('INUSE', 1, "On the phone"),
    ('ONHOLD', 1, "On hold"),
    ('BUSY', 1, "On the phone"),
    ('RINGING', 1, "Ringing"),
    ('UNAVAILABLE', 2, "Unavailable"),
    ('NOT_INUSE', 1, "Ready"),
    ('', 1, "Ready")  # Final state upon subscription teardown
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
