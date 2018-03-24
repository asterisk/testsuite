#!/usr/bin/env python
"""Asterisk Build Options Handling Unit Test

Copyright (C) 2011-2012, Digium, Inc.
Matt Jordan <mjordan@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
"""

from harness_shared import main
import unittest
from asterisk.buildoptions import AsteriskBuildOptions


class AsteriskBuildOptionsTests(unittest.TestCase):
    """Unit tests for AsteriskBuildOptions"""

    def test_1(self):
        """Test the defaults paths"""
        build_options = AsteriskBuildOptions()
        self.assertTrue(build_options)


if __name__ == "__main__":
    main()
