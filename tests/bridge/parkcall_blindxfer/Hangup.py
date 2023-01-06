#!/usr/bin/env python
'''
Copyright (C) 2013, Digium, Inc.
John Bigelow <jbigelow@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
'''

import sys
import logging

sys.path.append("lib/python")

LOGGER = logging.getLogger(__name__)


def handle_parkedcall(ami, event):
    parkee = event.get('parkeechannel')

    if parkee is None:
        LOGGER.error("Receved ParkedCall event without a Parkee.\n")
        return False

    LOGGER.info("Hanging up channel: %s" % parkee)
    ami.hangup(parkee)

    return True


def handle_testevent(ami, event):
    parkee = event.get('channel')

    if parkee is None:
        LOGGER.error("Received TestEvent without a channel.\n")

    if parkee == 'PJSIP/alice-00000004':
        # channel which parking failed for
        LOGGER.info("Hanging up channel: PJSIP/bob-00000005")
        ami.hangup('PJSIP/bob-00000005')
        # the call that was parked
        LOGGER.info("Hanging up channel: Local/fill-park@default-00000000;2")
        ami.hangup('Local/fill-park@default-00000000;2')
    elif parkee == 'PJSIP/alice-00000008':
        # channel which parking failed for
        LOGGER.info("Hanging up channel: PJSIP/bob-00000009")
        ami.hangup('PJSIP/bob-00000009')
        # the call that was parked
        LOGGER.info("Hanging up channel: Local/fill-park@default-00000001;2")
        ami.hangup('Local/fill-park@default-00000001;2')
    else:
        LOGGER.info("Hanging up channel: %s" % parkee)
        ami.hangup(parkee)

    return True
# vim:sw=4:ts=4:expandtab:textwidth=79
