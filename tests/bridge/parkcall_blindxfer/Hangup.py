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

def hangup_chan(ami, event):
    if ami.id != 0:
        return False

    if event.get('channel') == 'SIP/alice-00000004':
        # channel which parking failed for
        LOGGER.info("Hanging up channel: SIP/bob-00000005")
        ami.hangup('SIP/bob-00000005')
        # the call that was parked
        LOGGER.info("Hanging up channel: Local/fill-park@default-00000000;2")
        ami.hangup('Local/fill-park@default-00000000;2')
    elif event.get('channel') == 'SIP/alice-00000008':
        # channel which parking failed for
        LOGGER.info("Hanging up channel: SIP/bob-00000009")
        ami.hangup('SIP/bob-00000009')
        # the call that was parked
        LOGGER.info("Hanging up channel: Local/fill-park@default-00000001;2")
        ami.hangup('Local/fill-park@default-00000001;2')
    else:
        LOGGER.info("Hanging up channel: %s" % event.get('channel'))
        ami.hangup(event.get('channel'))

    return True

# vim:sw=4:ts=4:expandtab:textwidth=79
