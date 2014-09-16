#!/usr/bin/env python
"""Test snippet that drives the Status AMI action in the status test

Copyright (C) 2014, Digium, Inc.
Matt Jordan <mjordan@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
"""

def exec_status(ami, event):
    """Run the Status AMI action, then hangup

    Keyword Arguments:
    ami   The AMI connection
    event The event that triggered the callback
    """

    def _hangup_channels(result, ami, channel):
        ami.hangup(channel)
        return result

    # Get a list of channels
    message = {
        'action': 'Status',
        'AllVariables': 'true'
    }
    df = ami.collectDeferred(message, 'StatusComplete')
    df.addCallback(_hangup_channels, ami, "Local/s@default-00000000;1")

    return True
