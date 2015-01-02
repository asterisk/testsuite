#!/usr/bin/env python
# vim: sw=3 et:
"""
Copyright (C) 2010, Digium, Inc.

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
"""

from twisted.internet import reactor
from starpy import manager
import datetime
import logging
import re
import json
from pluggable_registry import PLUGGABLE_EVENT_REGISTRY,\
                               PLUGGABLE_ACTION_REGISTRY, var_replace

LOGGER = logging.getLogger(__name__)

class AMIEventInstance(object):
    """Base class for specific instances of AMI event observers

    This handles common elements for both headermatch and callback
    types of AMI event observers, allowing the individual types
    to focus on their specific duties.
    """

    def __init__(self, instance_config, test_object):
        """Constructor

        Keyword Arguments:
        instance_config The YAML configuration for the object
        test_object The main test object for the test
        """
        self.test_object = test_object
        conditions = instance_config['conditions']
        self.match_conditions = conditions['match']
        self.nonmatch_conditions = conditions.get('nomatch', {})
        self.ids = instance_config['id'].split(',') if 'id' in instance_config\
	    else ['0']
        self.action = instance_config['action'] if 'action' in instance_config\
            else 'none'
        self.config = instance_config
        self.passed = True
        self._registered = False
        self._event_observers = []
        self.count = {}

        if 'count' in instance_config:
            count = instance_config['count']
            if isinstance(count, int):
                # Need exactly this many events
                self.count['min'] = count
                self.count['max'] = count
            elif count[0] == '<':
                # Need at most this many events
                self.count['min'] = 0
                self.count['max'] = int(count[1:])
            elif count[0] == '>':
                # Need at least this many events
                self.count['min'] = int(count[1:])
                self.count['max'] = float("inf")
            else:
                # Need exactly this many events
                self.count['min'] = int(count)
                self.count['max'] = int(count)
        else:
            self.count['min'] = 0
            self.count['max'] = float("inf")

        self.count['event'] = 0
        if 'type' in instance_config and instance_config['type'] == 'cel':
            # If the type is 'cel' and no condition matches are defined in the
            # test's yaml then create the dict with setting the Event to 'CEL'.
            # Otherwise set Event to 'CEL' since it's the only Event we want.
            if instance_config['conditions']['match'] is None:
                instance_config['conditions']['match'] = {'Event' : 'CEL'}
                self.match_conditions = instance_config['conditions']['match']
            else:
                instance_config['conditions']['match']['Event'] = 'CEL'

        if 'Event' not in self.match_conditions:
            LOGGER.error("No event specified to match on. Aborting test")
            raise Exception

        test_object.register_ami_observer(self.ami_connect)
        test_object.register_stop_observer(self.__check_result)

    def ami_connect(self, ami):
        """AMI connect handler"""
        self.register_handler(ami)

    def register_handler(self, ami):
        """Register for the AMI events.

        Note:
        In general, most objects won't need this method.  You would only call
        this from a derived object when you create instances of the derived
        object after AMI connect.
        """
        if str(ami.id) in self.ids and not self._registered:
            LOGGER.debug("Registering event %s",
                         self.match_conditions['Event'])
            ami.registerEvent(self.match_conditions['Event'],
                              self.__event_callback)
            self._registered = True

    def register_event_observer(self, observer):
        """Register an observer to be called when a matched event is received

        An observer should take in two parameters:
        ami The AMI manager object
        event The received event
        """
        self._event_observers.append(observer)

    def dispose(self, ami):
        """Dispose of this object's AMI event registrations"""
        if str(ami.id) not in self.ids:
            LOGGER.warning("Unable to dispose of AMIEventInstance - " \
                           "unknown AMI object %d", ami.id)
            return
        ami.deregisterEvent(self.match_conditions['Event'],
                            self.__event_callback)

    def event_callback(self, ami, event):
        """Virtual method overridden by specific AMI Event instance types"""
        pass

    def __event_callback(self, ami, event):
        """Check event conditions to see if subclasses should be called into"""

        for key, value in self.match_conditions.items():
            if key.lower() not in event:
                LOGGER.debug("Condition %s not in event, returning", key)
                return
            if not re.match(value, event.get(key.lower())):
                LOGGER.debug("Condition %s: %s does not match %s: %s in event",
                             key, value, key, event.get(key.lower()))
                return
            else:
                LOGGER.debug("Condition %s: %s matches %s: %s in event",
                             key, value, key, event.get(key.lower()))

        for key, value in self.nonmatch_conditions.items():
            if key.lower() not in event:
                LOGGER.debug("Condition %s not in event, returning", key)
                return
            if re.match(value, event.get(key.lower())):
                LOGGER.debug("Condition %s: %s matches %s: %s in event",
                             key, value, key, event.get(key.lower()))
                return
            else:
                LOGGER.debug("Condition %s: %s does not match %s: %s in event",
                             key, value, key, event.get(key.lower()))

        self.count['event'] += 1

        # Conditions have matched up as expected so leave it to the individual
        # types to determine how to proceed
        for observer in self._event_observers:
            observer(ami, event)

        # If this event instance has met the minimum number execute any
        # specified action. Note that if min is 0 this will never get reached,
        # so something else must terminate the test
        if self.count['event'] == self.count['min']:
            if self.action == 'stop':
                self.test_object.stop_reactor()

        return self.event_callback(ami, event)

    def check_result(self, callback_param):
        """Virtual method to be overridden by subclasses"""
        pass

    def __check_result(self, callback_param):
        """Verify results

        This will check against event counts and the like and then call into
        overridden versions via check_result
        """
        if (self.count['event'] > self.count['max']
                or self.count['event'] < self.count['min']):
            LOGGER.warning("Event occurred %d times, which is out of the"
                           " allowable range", self.count['event'])
            LOGGER.warning("Event description: %s", str(self.config))
            self.test_object.set_passed(False)
            return callback_param
        return self.check_result(callback_param)


class AMIHeaderMatchInstance(AMIEventInstance):
    """A subclass of AMIEventInstance that operates by matching headers of
    AMI events to expected values. If a header does not match its expected
    value, then the test will fail
    """

    def __init__(self, instance_config, test_object):
        """Constructor

        Keyword Arguments:
        instance_config The YAML configuration for the object
        test_object The main test object for the test
        """
        super(AMIHeaderMatchInstance, self).__init__(instance_config,
                                                     test_object)
        LOGGER.debug("Initializing an AMIHeaderMatchInstance")
        if 'requirements' in instance_config:
            self.match_requirements =\
                    instance_config['requirements'].get('match', {})
            self.nonmatch_requirements =\
                    instance_config['requirements'].get('nomatch', {})
        else:
            self.match_requirements = {}
            self.nonmatch_requirements = {}

    def event_callback(self, ami, event):
        """Callback called when an event is received from AMI"""
        for key, value in self.match_requirements.items():
            if key.lower() not in event:
                LOGGER.warning("Requirement %s does not exist in event %s",
                               key, event['event'])
                self.passed = False
            elif not re.match(value, event.get(key.lower())):
                LOGGER.warning("Requirement %s: %s does not match %s: %s in " \
                               "event", key, value, key,
                               event.get(key.lower(), ''))
                self.passed = False
            else:
                LOGGER.debug("Requirement %s: %s matches %s: %s in event",
                             key, value, key, event.get(key.lower()))

        for key, value in self.nonmatch_requirements.items():
            if key.lower() not in event:
                LOGGER.warning("Requirement %s does not exist in event %s",
                               key, event['event'])
                self.passed = False
            elif re.match(value, event.get(key.lower(), '')):
                LOGGER.warning("Requirement %s: %s matches %s: %s in event",
                               key, value, key, event.get(key.lower(), ''))
                self.passed = False
            else:
                LOGGER.debug("Requirement %s: %s does not match %s: %s " \
                             "in event", key, value, key,
                             event.get(key.lower(), ''))

        return (ami, event)

    def check_result(self, callback_param):
        """Deferred callback called when this object should verify pass/fail"""
        self.test_object.set_passed(self.passed)
        return callback_param


class AMIOrderedHeaderMatchInstance(AMIEventInstance):
    """A subclass of AMIEventInstance that operates by matching headers of
    AMI events to expected values. If a header does not match its expected
    value, then the test will fail. This differs from AMIHeaderMatchInstance
    in that the order of specification is used to define an expected order
    for the events to arrive in which must be matched in order for the test
    to pass.
    """

    def __init__(self, instance_config, test_object):
        """Constructor

        Keyword Arguments:
        instance_config The YAML configuration for the object
        test_object The main test object for the test
        """
        super(AMIOrderedHeaderMatchInstance, self).__init__(instance_config,
                                                            test_object)
        LOGGER.debug("Initializing an AMIOrderedHeaderMatchInstance")
        self.match_index = 0
        self.match_requirements = []
        self.nonmatch_requirements = []
        for instance in instance_config['requirements']:
            self.match_requirements.append(instance.get('match', {}))
            self.nonmatch_requirements.append(instance.get('nomatch', {}))

    def event_callback(self, ami, event):
        """Callback called when an event is received from AMI"""
        if self.match_index >= len(self.match_requirements):
            LOGGER.debug("Event received and not defined: %s", event)
            return

        for key, value in self.match_requirements[self.match_index].items():
            if key.lower() not in event:
                LOGGER.warning("Requirement %s does not exist in event %s",
                               key, event['event'])
                self.passed = False
            elif not re.match(value, event.get(key.lower())):
                LOGGER.warning("Requirement %s: %s does not match %s: " \
                               "%s in event", key, value, key,
                               event.get(key.lower()))
                self.passed = False
            else:
                LOGGER.debug("Requirement %s: %s matches %s: %s in event",
                             key, value, key, event.get(key.lower()))

        for key, value in self.nonmatch_requirements[self.match_index].items():
            if key.lower() not in event:
                LOGGER.warning("Requirement %s does not exist in event %s",
                               key, event['event'])
                self.passed = False
            elif re.match(value, event.get(key.lower(), '')):
                LOGGER.warning("Requirement %s: %s matches %s: %s in event",
                               key, value, key, event.get(key.lower(), ''))
                self.passed = False
            else:
                LOGGER.debug("Requirement %s: %s does not match %s: %s "
                             "in event", key, value, key,
                             event.get(key.lower(), ''))

        self.match_index += 1
        return (ami, event)

    def check_result(self, callback_param):
        """Deferred callback called when this object should verify pass/fail"""
        self.test_object.set_passed(self.passed)
        return callback_param


class CelRequirement(object):
    """A particular set of requirements that should be matched on for CEL
    event checking
    """

    def __init__(self, requirements):
        """Constructor

        Keyword Arguments:
        requirements The CEL items to match on
        """
        self.requirements = {}

        # Make everything case insensitive for sanity
        for key, value in requirements['match'].items():
            lower_key = key.lower()
            if lower_key == 'extra':
                value = dict((key.lower(), value)\
                    for key, value in value.iteritems())
            self.requirements[lower_key] = value
        self.orderings = requirements.get('partialorder') or []
        self.named_id = requirements.get('id')

    def is_match(self, event):
        """Determine if this event matches us"""

        for key, value in event.items():
            item = self.requirements.get(key)
            if item is None:
                continue

            # test 'Extra' fields against the JSON blob
            if key == "extra":
                if not len(value):
                    continue
                extra_obj = json.loads(value)
                for extra_key, extra_value in extra_obj.items():
                    extra_item = item.get(extra_key.lower())
                    if extra_item is None:
                        continue
                    extra_match = re.match(extra_item, str(extra_value))
                    if extra_match is None or\
                        extra_match.end() != len(str(extra_value)):
                        LOGGER.debug('Skipping %s - %s does not equal %s for '
                                     'extra-subfield %s', event['eventname'],
                                     extra_item, str(extra_value), extra_key)
                        return False
            else:
                match = re.match(item, value)
                if match is None or match.end() != len(value):
                    LOGGER.debug('Skipping %s - %s does not equal %s '
                                 'for field %s', event['eventname'], item,
                                 value, key)
                    return False
        LOGGER.debug('Matched CEL event %s', event['eventname'])
        return True

    def __str__(self):
        return str(self.requirements)


class AMICelInstance(AMIEventInstance):
    """A subclass of AMIEventInstance that operates by matching headers of
    AMI CEL events to expected values. This is similar to
    AMIOrderedHeaderMatchInstance but differs in that it's specifically for
    checking CEL events and that a partial order may be specified to allow some
    events to be out of order.
    """

    # Class level list of all instances of this class
    ami_cel_instances = []

    # All matched expected events that have an ordering
    matched_cel_events = []

    # All unmatched expected events that have an ordering
    unmatched_cel_events = []

    def __init__(self, instance_config, test_object):
        """Constructor

        Keyword Arguments:
        instance_config The YAML configuration for the object
        test_object The main test object for the test
        """
        super(AMICelInstance, self).__init__(instance_config, test_object)

        self.match_requirements = []
        self.test_object.register_stop_observer(self._stop_callback)

        # Creat our requirements
        for instance in instance_config['requirements']:
            self.match_requirements.append(CelRequirement(instance))

        # Add of all our named events to the lists of events that haven't
        # occurred yet
        named_events = [ev for ev in self.match_requirements if\
            ev.named_id is not None]
        AMICelInstance.unmatched_cel_events.extend(named_events)

        AMICelInstance.ami_cel_instances.append(self)

    def event_callback(self, ami, event):
        """Callback called by the base class when an event matches"""

        if len(self.match_requirements) == 0:
            return

        LOGGER.debug("Received CEL event %s", str(event))

        req = self.match_requirements[0]
        if not req.is_match(event):
            LOGGER.debug("Dropping event %s - next required event is %s",
                         event['eventname'], req.requirements['eventname'])
            return

        self.match_requirements.pop(0)

        if len(req.orderings) > 0:
            self._check_orderings(req)

        if req.named_id is not None:
            AMICelInstance.unmatched_cel_events.remove(req)
            AMICelInstance.matched_cel_events.append(req)

    def _stop_callback(self, reason):
        """Stop observer on the test_object. Called when Asterisk has stopped
        at the end of the test"""

        if len(self.match_requirements) != 0:
            LOGGER.warning("Length of expected CEL requirements not zero: %d",
                           len(self.match_requirements))
            LOGGER.warning("Missed CEL requirement: %s",
                           str(self.match_requirements[0]))
            self.test_object.set_passed(False)
            return reason

        LOGGER.info("All expected CEL requirements matched")
        self.test_object.set_passed(True)
        return reason

    def _check_orderings(self, cel_requirement):
        """Check that this matched CelRequirement occurred in the right order"""

        for order_type, named_event in cel_requirement.orderings.items():
            order_type = order_type.lower()
            if order_type == 'after':
                matches = [ev for ev in AMICelInstance.matched_cel_events if\
                    ev.named_id == named_event]
                if len(matches) == 0:
                    LOGGER.warning('Event %s did not occur after %s; failing',
                                   str(cel_requirement), named_event)
                    self.test_object.set_passed(False)
            elif order_type == 'before':
                matches = [ev for ev in AMICelInstance.unmatched_cel_events if\
                    ev.named_id == named_event]
                if len(matches) == 0:
                    LOGGER.warning('Event %s did not occur before %s; failing',
                                   str(cel_requirement), named_event)
                    self.test_object.set_passed(False)
            else:
                LOGGER.warning('Unknown partialorder type %s; ignoring',
                               order_type)


class AMICallbackInstance(AMIEventInstance):
    """Subclass of AMIEventInstance that operates by calling a user-defined
    callback function. The callback function returns the current disposition
    of the test (i.e. whether the test is currently passing or failing).
    """

    def __init__(self, instance_config, test_object):
        """Constructor

        Keyword Arguments:
        instance_config The YAML configuration for the object
        test_object The main test object for the test
        """
        super(AMICallbackInstance, self).__init__(instance_config, test_object)
        self.callback_module = instance_config['callbackModule']
        self.callback_method = instance_config['callbackMethod']
        if 'start' in instance_config:
            self.passed = True if instance_config['start'] == 'pass' else False

    def event_callback(self, ami, event):
        """Callback called when an event is received from AMI"""
        callback_module = __import__(self.callback_module)
        method = getattr(callback_module, self.callback_method)
        self.passed = method(ami, event)
        if self.passed == None:
            LOGGER.error("Callback %s.%s returned None instead of a boolean",
                         self.callback_module, self.callback_method)
            self.passed = False

    def check_result(self, callback_param):
        """Deferred callback called when this object should verify pass/fail"""
        self.test_object.set_passed(self.passed)
        return callback_param

class AMIEventInstanceFactory:
    """Factory object that builds concrete instances of various AMIEventModules.

    Supported types:
    headermach - Construct a AMIHeaderMatchInstance object
    orderedheadermatch - Construct a AMIOrderedHeadermatchInstance object
    cel - Construct a AMICelInstance object
    callback - Construct a AMICallbackInstance object
    """

    @staticmethod
    def create_instance(instance_config, test_object):
        """Create an AMI event matching instance object

        Keyword Arguments:
        instance_config The instance object's configuration
        test_object The pluggable module framework's test object for the test
        """
        instance_type = instance_config['type']
        if instance_type == "headermatch":
            LOGGER.debug("instance type is 'headermatch'")
            return AMIHeaderMatchInstance(instance_config, test_object)
        elif instance_type == "orderedheadermatch":
            LOGGER.debug("instance type is 'orderedheadermatch'")
            return AMIOrderedHeaderMatchInstance(instance_config, test_object)
        elif instance_type == "cel":
            LOGGER.debug("instance type is 'cel'")
            return AMICelInstance(instance_config, test_object)
        elif instance_type == "callback":
            LOGGER.debug("instance type is 'callback'")
            return AMICallbackInstance(instance_config, test_object)
        else:
            LOGGER.error("Invalid type %s specified for AMI event instance",
                         instance_type)
            raise Exception

class AMIEventModule(object):
    """Pluggable module for AMI event matching

    This class acts as a very thin manager for multiple instances of objects
    derived from AMIEventInstance. It merely exists to create the objects and
    plug into the Pluggable Module Framework.
    """

    def __init__(self, module_config, test_object):
        """Constructor

        Keyword Arguments:
        instance_config The YAML configuration for the object
        test_object The main test object for the test
        """
        LOGGER.debug("Initializing AMIEvent module")
        self.test_object = test_object
        self.ami_instances = []
        for instance in module_config:
            event_instance = AMIEventInstanceFactory\
                .create_instance(instance, test_object)
            self.ami_instances.append(event_instance)

class AMI(object):
    """Class that manages a connection to Asterisk over AMI"""

    def __init__(self, on_login, on_error, timeout=60, user="mark",
                 secret="mysecret", host="127.0.0.1", port=5038):
        """Constructor

        Keyword Arguments:
        on_login Deferred callback to be called when user logs into AMI
        on_error Deferred callback to be called if an error occurs while logging
                 into AMI
        timeout  Time to wait before failing login attempts
        user     User to connect as
        secret   Password for the user
        host     Asterisk instance to connect to
        port     Port to connect on
        """
        self.on_login = on_login
        self.on_error = on_error
        self.login_timeout = timeout
        self.host = host
        self.port = port
        self._attempts = 0
        self._start = None
        self.ami = None
        self.ami_factory = manager.AMIFactory(user, secret)

    def login(self):
        """Start the login process"""

        self._attempts += 1
        LOGGER.debug("AMI Login attempt #%d", self._attempts)
        if not self._start:
            self._start = datetime.datetime.now()
        deferred = self.ami_factory.login(self.host, self.port)
        deferred.addCallbacks(self.on_login_success, self.on_login_error)

    def on_login_success(self, ami):
        """Deferred callback when login succeeds

        Keyword Arguments:
        ami The AMI Factory object
        """
        self.ami = ami
        LOGGER.debug("AMI Login succesful")
        return self.on_login(ami)

    def on_login_error(self, reason):
        """Deferred callback when login fails

        This will continue to attempt logging in until self.timeout is reached.
        If the timeout is reached, the login error deferred passed to the
        constructor is called.

        Keyword Arguments:
        reason The reason why the login attempt failed.
        """
        runtime = (datetime.datetime.now() - self._start).seconds
        if runtime >= self.login_timeout:
            LOGGER.error("AMI login failed after %d second timeout: %s",
                         self.login_timeout, reason.getErrorMessage())
            return self.on_error()
        delay = 2 ** self._attempts
        if delay + runtime >= self.login_timeout:
            delay = self.login_timeout - runtime
        reactor.callLater(delay, self.login)
        return reason

class AMIStartEventModule(object):
    """An event module that triggers when the test starts."""

    def __init__(self, test_object, triggered_callback, config):
        """Setup the test start observer"""
        self.test_object = test_object
        self.triggered_callback = triggered_callback
        self.config = config
        test_object.register_ami_observer(self.start_observer)

    def start_observer(self, ami):
        """Notify the event-action mapper that ami has started."""
        self.triggered_callback(self, ami)
PLUGGABLE_EVENT_REGISTRY.register("ami-start", AMIStartEventModule)

class AMIPluggableEventInstance(AMIHeaderMatchInstance):
    """Subclass of AMIEventInstance that works with the pluggable event action
    module.

    Events can be set to 'trigger-on-count' meaning (when set to True) the
    trigger callback will not be called until the min count is reached. For
    event/actions this means actions won't be executed until an event reaches
    its specified count.
    """

    def __init__(self, test_object, triggered_callback, config, data):
        """Setup the AMI event observer"""
        self.triggered_callback = triggered_callback
	self.data = data
        self.trigger_on_count = config.get('trigger-on-count', False)
        super(AMIPluggableEventInstance, self).__init__(config, test_object)

    def event_callback(self, ami, event):
        """Callback called when an event is received from AMI"""
	super(AMIPluggableEventInstance, self).event_callback(ami, event)
        if self.passed and (not self.trigger_on_count or
                            self.count['event'] == self.count['min']):
            self.triggered_callback(self.data, ami, event)


class AMIPluggableEventModule(object):
    """Generates AMIEventInstance instances that match events for the pluggable
    event-action framework.
    """
    def __init__(self, test_object, triggered_callback, config):
        """Setup the AMI event observers"""
        self.instances = []
        if not isinstance(config, list):
            config = [config]
        for instance in config:
            self.instances.append(AMIPluggableEventInstance(test_object,
                                                            triggered_callback,
                                                            instance,
                                                            self))
PLUGGABLE_EVENT_REGISTRY.register("ami-events", AMIPluggableEventModule)

def replace_ami_vars(mydict, values):
    outdict = {}
    for key, value in mydict.iteritems():
        outdict[key] = var_replace(value, values)

    return outdict

class AMIPluggableActionModule(object):
    """Pluggable AMI action module.
    """

    def __init__(self, test_object, config):
        """Setup the AMI event observer"""
        self.test_object = test_object
        if not isinstance(config, list):
            config = [config]
        self.config = config

    def run(self, triggered_by, source, extra):
        """Callback called when this action is triggered."""
        for instance in self.config:
            action = replace_ami_vars(instance["action"], extra)
            ami_id = instance.get("id", 0)
            self.test_object.ami[ami_id].sendMessage(action)
PLUGGABLE_ACTION_REGISTRY.register("ami-actions", AMIPluggableActionModule)
