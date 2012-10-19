#!/usr/bin/env python
'''
Copyright (C) 2012, Digium, Inc.
Kinsey Moore <kmoore@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
'''


def hangup_call(ami, event):
    '''This hangs up the last remaining call path for the IPv6 attended
    transfer test, causing the test to end instead of waiting for it to time
    out after 30 seconds.'''
    ami.hangup("SIP/end_b-00000001")
    return True
