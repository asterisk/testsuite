#!/usr/bin/env python
"""Module for testing the message_match module.

Copyright (C) 2018, Digium, Inc.
Kevin Harwell <kharwell@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
"""

import logging
import sys
import unittest

sys.path.append('lib/python')  # noqa
from asterisk.matcher import PluggableConditions


LOGGER = logging.getLogger(__name__)


class TestObject(object):
    """Simple test object that implements methods used by message
    match conditions.
    """

    def __init__(self):
        """Constructor"""

        self.passed = True

    def set_passed(self, passed):
        """Set the passed value"""

        self.passed = passed

    def stop_reactor(self):
        """Noop"""

        pass

    def register_stop_observer(self, callback):
        """Noop"""

        pass


class PluggableConditionsTests(unittest.TestCase):
    """Unit tests for message match conditions."""

    def setUp(self):
        """Setup test object"""

        self.test_object = TestObject()

    def test_001_defaults(self):
        """Test condition defaults"""

        config = {'conditions': ['hello']}

        conditions = PluggableConditions(config, self.test_object)

        self.assertTrue(conditions.check('hello'))
        self.assertTrue(conditions.check_final())

    def test_002_match(self):
        """Test basic matching"""

        config = {
            'conditions': [
                {'match': 'hello'}
            ]
        }

        conditions = PluggableConditions(config, self.test_object)

        self.assertTrue(conditions.check('hello'))
        self.assertTrue(conditions.check_final())

    def test_003_optional(self):
        """Test optional matching"""

        config = {
            'conditions': [
                {'optional': 'hello'}
            ]
        }

        conditions = PluggableConditions(config, self.test_object)

        # Check with no message handled
        self.assertTrue(conditions.check_final())

        # Now check once message handled
        self.assertTrue(conditions.check('hello'))
        self.assertTrue(conditions.check_final())

    def test_004_count(self):
        """Test count condition"""

        config = {
            'conditions': [
                {'match': 'hello', 'count': '2'}
            ]
        }

        conditions = PluggableConditions(config, self.test_object)

        # Check with no message handled
        self.assertFalse(conditions.check_final())

        # Check with one message handled
        self.assertFalse(conditions.check('hello'))
        self.assertFalse(conditions.check_final())

        # Check with two messages handled
        self.assertTrue(conditions.check('hello'))
        self.assertTrue(conditions.check_final())

        # Check with three messages handled
        self.assertFalse(conditions.check('hello'))
        self.assertTrue(conditions.check_final())  # min met

    def test_005_count(self):
        """Test range count condition"""

        config = {
            'conditions': [
                {'match': 'hello', 'count': '2-4'}
            ]
        }

        conditions = PluggableConditions(config, self.test_object)

        # Check with no message handled
        self.assertFalse(conditions.check_final())

        # Check with one message handled
        self.assertFalse(conditions.check('hello'))
        self.assertFalse(conditions.check_final())

        # Check with two messages handled
        self.assertTrue(conditions.check('hello'))
        self.assertTrue(conditions.check_final())

        # Check with four messages handled
        self.assertTrue(conditions.check('hello'))
        self.assertTrue(conditions.check('hello'))
        self.assertTrue(conditions.check_final())

        # Check with five messages handled
        self.assertFalse(conditions.check('hello'))
        self.assertTrue(conditions.check_final())  # min met

    def test_006_min(self):
        """Test minimum condition"""

        config = {
            'conditions': [
                {'match': 'hello', 'count': '>1'}
            ]
        }

        conditions = PluggableConditions(config, self.test_object)

        # Check with no message handled
        self.assertFalse(conditions.check_final())

        # Check with one message handled
        self.assertFalse(conditions.check('hello'))
        self.assertFalse(conditions.check_final())

        # Check with two messages handled
        self.assertTrue(conditions.check('hello'))
        self.assertTrue(conditions.check_final())

    def test_007_max(self):
        """Test maximum condition"""

        config = {
            'conditions': [
                {'match': 'hello', 'count': '<2'}
            ]
        }

        conditions = PluggableConditions(config, self.test_object)

        # Check with no message handled
        self.assertTrue(conditions.check_final())

        # Check with one message handled
        self.assertTrue(conditions.check('hello'))
        self.assertTrue(conditions.check_final())

        # Check with two messages handled
        self.assertFalse(conditions.check('hello'))
        self.assertTrue(conditions.check_final())  # min met

    def test_008_max(self):
        """Test no match condition"""

        config = {
            'conditions': [
                {'match': 'hello', 'count': '0'}
            ]
        }

        conditions = PluggableConditions(config, self.test_object)

        # Check with no message handled
        self.assertTrue(conditions.check_final())

        # Check with one message handled
        self.assertFalse(conditions.check('hello'))
        self.assertTrue(conditions.check_final())  # min met

    def test_009_trigger_on_any(self):
        """Test trigger on any option"""

        config = {
            'trigger-on-any': True,
            'conditions': [
                {'match': 'hello', 'count': '1'},
                {'match': 'world', 'count': '2'}
            ]
        }

        conditions = PluggableConditions(config, self.test_object)

        self.assertFalse(conditions.check('world'))
        self.assertFalse(conditions.check_final())

        self.assertTrue(conditions.check('hello'))  # 'hello' is met
        self.assertFalse(conditions.check_final())  # 'world' not me

        conditions = PluggableConditions(config, self.test_object)

        self.assertFalse(conditions.check('world'))
        self.assertFalse(conditions.check_final())

        self.assertTrue(conditions.check('world'))  # 'world' is met
        self.assertFalse(conditions.check_final())  # 'hello' not met

    def test_010_trigger_on_all(self):
        """Test trigger on all option"""

        config = {
            'trigger-on-all': True,
            'conditions': [
                {'match': 'hello', 'count': '1'},
                {'match': 'world', 'count': '2'}
            ]
        }

        conditions = PluggableConditions(config, self.test_object)

        self.assertFalse(conditions.check('world'))
        self.assertFalse(conditions.check_final())

        self.assertFalse(conditions.check('hello'))  # 'world' not met
        self.assertFalse(conditions.check_final())

        self.assertTrue(conditions.check('world'))
        self.assertTrue(conditions.check_final())

    def test_010_trigger_on_first(self):
        """Test trigger on first match (other conditions don't apply)"""

        config = {
            'trigger-on-any': False,
            'trigger-on-all': False,
            'conditions': [
                {'match': 'hello', 'count': '1'},
                {'match': 'world', 'count': '2'}
            ]
        }

        conditions = PluggableConditions(config, self.test_object)

        self.assertTrue(conditions.check('world'))
        self.assertFalse(conditions.check_final())  # 'hello' & 'world' not met


if __name__ == "__main__":
    """Run the unit tests"""

    logging.basicConfig(stream=sys.stdout, level=logging.DEBUG,
                        format="%(module)s:%(lineno)d - %(message)s")
    unittest.main()
