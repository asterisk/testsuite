"""
Copyright (C) 2014, Digium, Inc.
Kinsey Moore <kmoore@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
"""

import logging

LOGGER = logging.getLogger(__name__)

HUNGUP = 0

def transfer_complete(ami, event):
    global HUNGUP
    HUNGUP += 1
    if HUNGUP == 2:
        LOGGER.debug("Hanging up all charlie channels")
        ami.hangup("/^PJSIP/charlie-.*$/")
    return True
