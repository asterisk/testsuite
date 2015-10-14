#/usr/bin/env python
"""
Copyright (C) 2015, Digium, Inc.
Ashley Sanders <asanders@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
"""

import sys

sys.path.append('lib/python')
sys.path.append('tests/channels/pjsip/subscriptions/rls')


class ValidationInfo(object):
    """Lightweight helper class for storing the validation business logic."""

    def __init__(self, resources, version, fullstate, rlmi, rlmi_name):
        """Constructor.

        Keyword Arguments:
        resources              -- A dictionary of the resource names and their
                                  expected state.
        version                -- The expected RLMI version attribute.
                                  Expressed as an integer.
        fullstate              -- The expected RLMI fullState attribute.
                                  Expressed as a boolean.
        rlmi                   -- The RLMI part of the packet.
        rlmi_name              -- The expected RLMI name element value.
        """

        self.resources = resources
        self.version = version
        self.fullstate = fullstate
        self.rlmi = rlmi
        self.rlmi_name = rlmi_name
