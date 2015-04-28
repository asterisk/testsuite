#!/usr/bin/env python
"""
Copyright (C) 2015, Digium, Inc.
Ashley Sanders <asanders@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
"""

import sys

sys.path.append("lib/python")
sys.path.append("tests/channels/pjsip/configuration")

from test_harness import TestHarness


class DuplicateSectionsTestHarness(TestHarness):
    """The test harness for the duplicate sections test."""

    def __init__(self, config, test_object):
        """Constructor.

        Keyword Arguments:
        config                 -- The YAML configuration for this test.
        test_object            -- The TestCaseModule instance for this test.
        """

        # The cli options for the 'pjsip show' command
        super(DuplicateSectionsTestHarness, self).__init__(config,
                                                           test_object)

    def load_config(self, config):
        """Loads the module configuration.

        Keyword Arguments:
        config                 -- The YAML configuration for this test.
        """

        super(DuplicateSectionsTestHarness, self).load_config(config)
