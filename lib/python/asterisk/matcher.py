"""Module for handling pattern and conditional message matching and
aggregation.

Copyright (C) 2018, Digium, Inc.
Kevin Harwell <kharwell@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
"""

import logging

from test_suite_utils import all_match
from pluggable_registry import PLUGGABLE_EVENT_REGISTRY,\
    PLUGGABLE_ACTION_REGISTRY


LOGGER = logging.getLogger(__name__)


class ConditionError(Exception):
    """Error raised a condition(s) fail"""

    def __init__(self, failures):
        """Create a condition(s) error exception.

        Keyword Arguments:
        failures - A list of failed condition objects
        """

        if not isinstance(failures, list):
            failures = [failures]

        msg = ''
        for f in failures:
            msg += f.error() + '\n'

        super(ConditionError, self).__init__(msg)


class Condition(object):

    @staticmethod
    def create(config, match_fun=None):
        """Create a condition object from the given configuration.

        Keyword Arguments:
        config - Data in a dictionary format used in object creation
        match_fun - The function used to match the pattern and value

        Configuration options:
        match - A regex string, dictionary, or list.
        count - Expected number of matches. Can be a single value (ex: 2),
            range (ex: 2-5), or a lower (ex: <4) or upper (ex: >2) limit.
        optional - alias for 'match' and expects 0 or 1 matches.
        """

        if isinstance(config, str) or isinstance(config, unicode):
            config = {'match': config}

        if 'optional' in config:
            config['match'] = config['optional']
            minimum = '<2'
        else:
            minimum, _, maximum = str(config.get('count', '1')).partition('-')

        if minimum.startswith('>'):
            minimum = int(minimum[1:]) + 1
            maximum = float('inf')
        elif minimum.startswith('<'):
            maximum = int(minimum[1:]) - 1
            minimum = 0
        else:
            minimum = int(minimum)
            maximum = int(maximum) if maximum else minimum

        if minimum > maximum:
            raise SyntaxError("Invalid count: minimum '{0}' can't be greater "
                              "than maximum '{1}'".format(minimum, maximum))

        return Condition(config.get('match'), minimum, maximum)

    def __init__(self, pattern=None, minimum=1, maximum=1, match_fun=None):
        """Constructor

        Keyword Arguments:
        pattern - The pattern that will be checked against
        minimum - The expected minimum number of matches
        maximum - The expected maximum number of matches
        match_fun - The function used to match the pattern and value
        """

        self.pattern = pattern
        self.minimum = minimum
        self.maximum = maximum
        self.match_fun = match_fun or all_match

        self.count = 0

    def check_match(self, value):
        """Check if the given value matches the expected pattern.

        Keyword Arguments:
        value - The value to check against the expected pattern
        """

        if self.match_fun(self.pattern, value):
            LOGGER.debug("Matched condition: {0}".format(self.pattern))
            self.count += 1
            return True

        return False

    def check_max(self):
        """Check if the current match count is less than or equal to the
        configured maximum.
        """

        return self.count <= self.maximum

    def check_min(self):
        """Check if the current match count is greater than or equal to the
        configured minimum.
        """

        return self.count >= self.minimum

    def error(self):
        """Error out the conditional."""

        return ("\nCondition: '{0}'\nExpected >= {1} and <= {2} but "
                "received {3}".format(self.pattern, self.minimum,
                                      self.maximum, self.count))


class Conditions(object):

    @staticmethod
    def create(config, on_match=None, match_fun=None):
        """Create a conditions object from the given configuration.

        Keyword Arguments:
        config - Data in a dictionary format used in object creation
        on_match - Optional callback to raise on a match. Handler Must be
            proto-typed as 'handler(matched, value)'
        match_fun - Optional function used to match the pattern and value

        Configuration options:
        conditions - A list of condition configuration data
        trigger-on-any - Raise the 'on_match' event if any condition has been
            fully met (meaning at least one match with all its minimum met).
            Defaults to False
        trigger-on-all - Raise the 'on_match' event if all conditions have been
            fully met (meaning all have matched and met their minimum).
            Defaults to True

        Note:
        If both trigger-on-any and trigger-on-all are False then the 'on_match'
        event is raised upon the first basic match (meaning a minimum may or
        may not have been met yet)
        """

        conditions = []
        for c in config['conditions']:
            conditions.append(Condition.create(c, match_fun))

        # Any is checked prior to all, so okay for all to also be True
        return Conditions(conditions, config.get('trigger-on-any', False),
                          config.get('trigger-on-all', True), on_match)

    def __init__(self, conditions, trigger_on_any=False, trigger_on_all=True,
                 on_match=None):
        """Constructor

        Keyword Arguments:
        conditions - A list of condition objects
        trigger_on_any - check returns true if any condition is met
        trigger_on_all - check returns true if all conditions are met
        on_match - Optional callback to raise on a match. Handler Must be
            proto-typed as 'handler(matched, value)'
        """

        self.conditions = conditions or []
        self.trigger_on_any = trigger_on_any
        self.trigger_on_all = trigger_on_all
        self.on_match = on_match or (lambda y, z: None)

    def check(self, value):
        """Check if the given value matches a stored pattern, and if so then
        also make sure that any other relevant conditional criteria have been
        met.

        Keyword Arguments:
        value - The value to check against the patterns

        Return:
        True given the following, false otherwise:
            trigger_on_any was set and at least one required conditional
            was met.

            trigger_on_all was set and all required conditional were met.

            An item matched, and neither of the above parameters were set.
        """

        matched = []
        for c in self.conditions:
            if not c.check_match(value):
                continue

            if not c.check_max():
                raise ConditionError(c)

            matched.append(c)


        if not matched:
            return False

        if self.trigger_on_any:
            if not any(c.check_min() for c in matched):
                return False
        elif self.trigger_on_all:
            if not all(c.check_min() for c in self.conditions):
                return False

        LOGGER.debug("Conditions triggered: {0}".format([c.pattern for c in matched]))
        self.on_match(matched, value)
        return True

    def check_final(self):
        """Check final conditionals and fail on those not met."""

        failures = [c for c in self.conditions if not c.check_min()]
        if failures:
            raise ConditionError(failures)
        return True


class PluggableConditions(object):

    def __init__(self, config, test_object, on_match=None):
        """Constructor

        Keyword Arguments:
        config - Configuration for this module
        test_object - The test case driver
        on_match - Optional callback to raise on a match. Handler Must be
            proto-typed as 'handler(matched, value)'
        """

        self.config = config
        self.test_object = test_object
        self.test_object.register_stop_observer(self.__handle_stop)

        self.conditions = Conditions.create(self.config, on_match)

    def fail_and_stop(self, error_msg):
        """Fail the test and stop the reactor.

        Keyword Arguments:
        error_msg - The error message to log
        """

        LOGGER.error(error_msg)

        self.test_object.set_passed(False)
        self.test_object.stop_reactor()

    def check(self, value):
        try:
            return self.conditions.check(value)
        except ConditionError as e:
            self.fail_and_stop(e)

    def check_final(self):
        if self.test_object.passed:
            try:
                self.conditions.check_final()
            except ConditionError as e:
                self.fail_and_stop(e)
        return self.test_object.passed

    def __handle_stop(self, *args):
        """Check any final conditions prior to test end.

        Keyword Arguments:
        args: Unused
        """

        self.check_final()


class PluggableConditionsEventModule(object):
    """Registry wrapper for pluggable conditional event checks."""

    def __init__(self, test_object, triggered_callback, config):
        """Constructor

        Keyword Arguments:
        test_object - The TestCase driver
        triggered_callback - Conditionally called when matched
        config - Configuration for this module

        Configuration options:
        type - The <module.class> of the object type to create that is
            listens for events and passes event data to the conditional
            matcher.
        """

        self.triggered_callback = triggered_callback

        module_name, _, obj_type = config['type'].partition('.')

        module = __import__(module_name, fromlist=[obj_type])
        if not module:
            raise Exception("Unable to import module '{0}'.".format(module_name))

        obj = getattr(module, obj_type)

        self.conditions = obj(config, test_object, self.__handle_match)

    def __handle_match(self, matched, event):
        self.triggered_callback(self, matched, event)


PLUGGABLE_EVENT_REGISTRY.register('event', PluggableConditionsEventModule)
