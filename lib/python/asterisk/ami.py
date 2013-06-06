from twisted.internet import reactor, protocol
from starpy import manager
import datetime
import sys
import logging
import re

logger = logging.getLogger(__name__)

class AMIEventInstance(object):
    '''
    Base class for specific instances of AMI event observers

    This handles common elements for both headermatch and callback
    types of AMI event observers, allowing the individual types
    to focus on their specific duties.
    '''
    def __init__(self, instance_config, test_object):
        self.test_object = test_object
        self.match_conditions = instance_config['conditions']['match']
        self.nonmatch_conditions = instance_config['conditions'].get('nomatch', {})
        self.ids = instance_config['id'].split(',') if 'id' in instance_config else ['0']
        self.config = instance_config
        self.passed = True
        self._registered = False

        if 'count' in instance_config:
            count = instance_config['count']
            if isinstance(count, int):
                # Need exactly this many events
                self.count_min = count
                self.count_max = count
            elif count[0] == '<':
                # Need at most this many events
                self.count_min = 0
                self.count_max = int(count[1:])
            elif count[0] == '>':
                # Need at least this many events
                self.count_min = int(count[1:])
                self.count_max = float("inf")
            else:
                # Need exactly this many events
                self.count_min = int(count)
                self.count_max = int(count)
        else:
            self.count_min = 0
            self.count_max = float("inf")

        self.event_count = 0

        if instance_config['type'] == 'cel':
            # If the type is 'cel' and no condition matches are defined in the
            # test's yaml then create the dict with setting the Event to 'CEL'.
            # Otherwise set Event to 'CEL' since it's the only Event we want.
            if instance_config['conditions']['match'] is None:
                instance_config['conditions']['match'] = {'Event' : 'CEL'}
                self.match_conditions = instance_config['conditions']['match']
            else:
                instance_config['conditions']['match']['Event'] = 'CEL'

        if 'Event' not in self.match_conditions:
            logger.error("No event specified to match on. Aborting test")
            raise Exception

        test_object.register_ami_observer(self.ami_connect)
        test_object.register_stop_observer(self.__check_result)

    def ami_connect(self, ami):
        self.register_handler(ami)

    def register_handler(self, ami):
        ''' Register for the AMI events.

        Note:
        In general, most objects won't need this method.  You would only call
        this from a derived object when you create instances of the derived
        object after AMI connect.
        '''
        if str(ami.id) in self.ids and not self._registered:
            logger.debug("Registering event %s" % self.match_conditions['Event'])
            ami.registerEvent(self.match_conditions['Event'], self.__event_callback)
            self._registered = True

    def dispose(self, ami):
        ''' Dispose of this object's AMI event registrations '''
        if str(ami.id) not in self.ids:
            logger.warning("Unable to dispose of AMIEventInstance - unknown AMI object %d" % ami.id)
            return
        ami.deregisterEvent(self.match_conditions['Event'], self.__event_callback)

    def event_callback(self, ami, event):
        '''
        Virtual method overridden by specific AMI Event
        instance types
        '''
        pass

    def __event_callback(self, ami, event):
        '''
        Check event conditions to see if subclasses should
        be called into
        '''

        for k,v in self.match_conditions.items():
            if k.lower() not in event:
                logger.debug("Condition %s not in event, returning" % (k))
                return
            if not re.match(v, event.get(k.lower())):
                logger.debug("Condition %s: %s does not match %s: %s in event" %
                        (k, v, k, event.get(k.lower())))
                return
            else:
                logger.debug("Condition %s: %s matches %s: %s in event" %
                        (k, v, k, event.get(k.lower())))

        for k,v in self.nonmatch_conditions.items():
            if k.lower() not in event:
                logger.debug("Condition %s not in event, returning" % (k))
                return
            if re.match(v, event.get(k.lower())):
                logger.debug("Condition %s: %s matches %s: %s in event" %
                        (k, v, k, event.get(k.lower())))
                return
            else:
                logger.debug("Condition %s: %s does not match %s: %s in event" %
                        (k, v, k, event.get(k.lower())))

        self.event_count += 1

        #Conditions have matched up as expected
        #so leave it to the individual types to determine
        #how to proceed

        return self.event_callback(ami, event)

    def check_result(self, callback_param):
        '''Virtual method to be overridden by subclasses'''
        pass

    def __check_result(self, callback_param):
        '''
        This will check against event counts and the like and then
        call into overridden veresions
        '''
        if (self.event_count > self.count_max
                or self.event_count < self.count_min):
            logger.warning("Event occurred %d times, which is out of the"
                    " allowable range" % self.event_count)
            logger.warning("Event description: %s" % (str(self.config)))
            self.test_object.set_passed(False)
            return callback_param
        return self.check_result(callback_param)

class AMIHeaderMatchInstance(AMIEventInstance):
    '''
    A subclass of AMIEventInstance that operates by matching headers of
    AMI events to expected values. If a header does not match its expected
    value, then the test will fail
    '''
    def __init__(self, instance_config, test_object):
        super(AMIHeaderMatchInstance, self).__init__(instance_config, test_object)
        logger.debug("Initializing an AMIHeaderMatchInstance")
        if 'requirements' in instance_config:
            self.match_requirements = (
                    instance_config['requirements'].get('match', {}))
            self.nonmatch_requirements = (
                    instance_config['requirements'].get('nomatch', {}))
        else:
            self.match_requirements = {}
            self.nonmatch_requirements = {}

    def event_callback(self, ami, event):
        for k,v in self.match_requirements.items():
            if not re.match(v, event.get(k.lower())):
                logger.warning("Requirement %s: %s does not match %s: %s in event" %
                        (k, v, k, event.get(k.lower())))
                self.passed = False
            else:
                logger.debug("Requirement %s: %s matches %s: %s in event" %
                        (k, v, k, event.get(k.lower())))

        for k,v in self.nonmatch_requirements.items():
            if re.match(v, event.get(k.lower(), '')):
                logger.warning("Requirement %s: %s matches %s: %s in event" %
                        (k, v, k, event.get(k.lower(), '')))
                self.passed = False
            else:
                logger.debug("Requirement %s: %s does not match %s: %s in event" %
                        (k, v, k, event.get(k.lower(), '')))

        return (ami, event)

    def check_result(self, callback_param):
        self.test_object.set_passed(self.passed)
        return callback_param

class AMIOrderedHeaderMatchInstance(AMIEventInstance):
    '''
    A subclass of AMIEventInstance that operates by matching headers of
    AMI events to expected values. If a header does not match its expected
    value, then the test will fail. This differs from AMIHeaderMatchInstance
    in that the order of specification is used to define an expected order
    for the events to arrive in which must be matched in order for the test
    to pass.
    '''
    def __init__(self, instance_config, test_object):
        super(AMIOrderedHeaderMatchInstance, self).__init__(instance_config, test_object)
        logger.debug("Initializing an AMIOrderedHeaderMatchInstance")
        self.match_index = 0
        self.match_requirements = []
        self.nonmatch_requirements = []
        for instance in instance_config['requirements']:
            self.match_requirements.append(
                    instance.get('match', {}))
            self.nonmatch_requirements.append(
                    instance.get('nomatch', {}))

    def event_callback(self, ami, event):
        if self.match_index >= len(self.match_requirements):
            logger.debug("Event received and not defined: %s" % event)
            return

        for k,v in self.match_requirements[self.match_index].items():
            if not re.match(v, event.get(k.lower())):
                logger.warning("Requirement %s: %s does not match %s: %s in event" %
                        (k, v, k, event.get(k.lower())))
                self.passed = False
            else:
                logger.debug("Requirement %s: %s matches %s: %s in event" %
                        (k, v, k, event.get(k.lower())))

        for k,v in self.nonmatch_requirements[self.match_index].items():
            if re.match(v, event.get(k.lower(), '')):
                logger.warning("Requirement %s: %s matches %s: %s in event" %
                        (k, v, k, event.get(k.lower(), '')))
                self.passed = False
            else:
                logger.debug("Requirement %s: %s does not match %s: %s in event" %
                        (k, v, k, event.get(k.lower(), '')))

        self.match_index += 1
        return (ami, event)

    def check_result(self, callback_param):
        self.test_object.set_passed(self.passed)
        return callback_param

class AMICel(AMIEventInstance):
    '''
    A subclass of AMIEventInstance that operates by matching headers of
    AMI CEL events to expected values. This is similar to
    AMIOrderedHeaderMatchInstance but differs in that it's specifically for
    checking CEL events and that a partial order may be specified to allow some
    events to be out of order.
    '''
    def __init__(self, instance_config, test_object):
        super(AMICel, self).__init__(instance_config, test_object)
        self.match_index = 0
        self.submatch_index = None
        self.cel_ids = []
        self.match_requirements = []
        self.partial_order_requirements = []
        self.cel_eventnames = []
        self.matched_events = []
        self.marked_failed = False

        for instance in instance_config['requirements']:
            if 'id' not in instance:
                logger.error("No 'id' keyword was found for a cel requirement "
                        "in the test's yaml file.")
                raise Exception

            if not instance['id']:
                logger.error("No value found for the 'id' keyword of a cel "
                        "requirement in the test's yaml file.")
                raise Exception

            if instance['id'] in self.cel_ids:
                logger.error("The cel id '%s' is a duplicate. ID's must be "
                        "unique." % instance['id'])
                raise Exception

            self.cel_ids.append(instance['id'])

            self.match_requirements.append(
                    instance.get('match', {}))

            if 'partialorder' not in instance:
                self.partial_order_requirements.append(
                        instance.get('partialorder',
                            {'after' : None, 'before' : None}))
            else:
                tmp = {}
                origpartorder = instance['partialorder']
                for k,v in origpartorder.items():
                    # Don't change an int of 0 to None. This allows it to be
                    # caught in the regex later in case the single quotes were
                    # forgotten in the config.
                    if not v and v != 0 and v is not None:
                        tmp[k] = None
                    else:
                        tmp[k] = v

                if 'after' not in tmp:
                    tmp['after'] = None
                if 'before' not in tmp:
                    tmp['before'] = None
                self.partial_order_requirements.append(tmp)

        self.__verify_match_requirements(self.match_requirements)

        # Remove any duplicates from our list of CEL EventName's
        self.cel_eventnames = list(set(self.cel_eventnames))

    def __verify_match_requirements(self, match_requirements):
        cel_cnt = 0

        for item in range(0, len(match_requirements)):
            # Fixup empty strings defined in the test's yaml file.
            for k, v in match_requirements[item].items():
                if not v:
                    logger.debug("No expected header for '%s', using '^$'" % k)
                    match_requirements[item][k] = '^$'
            # Build list of CEL EventName's from test's yaml file. Used later on to
            # ignore any received event where the EventName is not found in this list.
            if "EventName" not in match_requirements[item]:
                logger.error("No EventName specified. Aborting test.")
                raise Exception
            eventname = match_requirements[item].get('EventName')
            if eventname is None:
                logger.error("No value found for 'EventName' or it's not "
                        "defined in the test's yaml file. Aborting test.")
                raise Exception

            self.cel_eventnames.append(eventname)

            # Check if 'after' is found in the test's yaml file for this event
            # requirement and if it's a string of one or more digits.
            after = self.partial_order_requirements[item].get('after')
            if after is not None:
                try:
                    if not re.match('^[a-zA-Z0-9_-]*$', after):
                        logger.error("CEL ID '%s': The value of 'after' must "
                                "be a string. Aborting test." %
                                self.cel_ids[cel_cnt])
                        raise Exception
                except TypeError:
                    logger.error("CEL ID '%s': The value of 'after' must be a "
                            "string. Aborting test." %
                            self.cel_ids[cel_cnt])
                    raise Exception

            # Check if 'before' is found in the test's yaml file for this event
            # requirement and if it's a string of one or more digits.
            before = self.partial_order_requirements[item].get('before')
            if before is not None:
                try:
                    if not re.match('^[a-zA-Z0-9_-]*$', before):
                        logger.error("CEL id '%s': The value of 'before' must "
                                "be a string. Aborting test." %
                                self.cel_ids[cel_cnt])
                        raise Exception
                except TypeError:
                    logger.error("CEL ID '%s': The value of 'before' must be "
                            "a string. Aborting test." %
                            self.cel_ids[cel_cnt])
                    raise Exception

            # Get dict from list for whatever index we are on:
            d = match_requirements[item]

            # Convert the dict keys to lowercase but leave the values as is for our
            # expected event.
            tmp = [(k.lower(),v) for k,v in d.items()]
            match_requirements.append(dict(tmp))
            cel_cnt += 1

        # Remove the orignal items leaving only those whose keys are now lower
        # case
        for x in range(0, cel_cnt):
            match_requirements.pop(0)

        return match_requirements

    def event_callback(self, ami, event):
        # Ignore any received CEL events where the EventName is not a
        # requirement listed in the test's yaml.
        eventname = event.get('eventname')
        if eventname not in self.cel_eventnames:
            logger.debug("Ignoring CEL EventName '%s'" % eventname)
            return

        # Check if we already made a match for this expected event. If so then
        # skip it.
        for m in range(self.match_index, len(self.match_requirements)):
            if self.cel_ids[self.match_index] in self.matched_events:
                logger.info("Skipping requirement ID '%s' since we already "
                        "matched it." % self.cel_ids[self.match_index])
                self.match_index += 1

        logger.info("Expecting requirement ID '%s'" %
                self.cel_ids[self.match_index])
        # Get dict from list for whatever index we are on:
        expected = self.match_requirements[self.match_index]

        for k,v in expected.items():
            if self.marked_failed: return
            if k not in event.keys():
                self.mark_failed('nokey', self.cel_ids[self.match_index], k, event)
                return
            if not re.match(v, event.get(k)):
                match_found = False
                submatch_found = False
                logger.debug("A requirement 'match' was NOT met against "
                        "requirement ID '%s'" % self.cel_ids[self.match_index])
                # Check partial order to see if being out of order is allowed
                self.check_partorder_exists(self.match_index, event,
                        match_found)
                if self.marked_failed: return
                # See if this received event matches any other requirements.
                submatch_found = self.find_requirement_match(event)
                if self.marked_failed: return
                # Now lets see if this requirement has a partial order specified
                self.check_partorder_exists(self.submatch_index, event,
                        match_found, submatch_found)
            else:
                match_found = True
                logger.debug("A requirement 'match' was met against "
                        "requirement ID '%s'" % self.cel_ids[self.match_index])
                self.check_partorder_exists(self.match_index, event,
                        match_found)

        if self.submatch_index is not None:
            logger.info("All criteria has been met for requirement ID '%s'" %
                    self.cel_ids[self.submatch_index])
            self.matched_events.append(self.cel_ids[self.submatch_index])
            self.submatch_index = None
            # Not incrementing self.match_index here since we're still
            # expecting the requirement that we haven't successfully matched to
        else:
            logger.info("All criteria has been met for requirement ID '%s'" %
                    self.cel_ids[self.match_index])
            self.matched_events.append(self.cel_ids[self.match_index])
            # Increment so we expect a new requirement since we matched the
            # one we were on.
            self.match_index += 1

        logger.debug("Matched requirements so far: %s" % self.matched_events)
        return (ami, event)

    def check_partorder_exists(self, index, event, match_found,
            submatch_found = None):
        after = self.partial_order_requirements[index].get('after')
        before = self.partial_order_requirements[index].get('before')
        # If a before/after partial order isn't defined for this expected event
        # then we must fail it as the expected event did not match the
        # received event.
        logger.debug("Checking if partial order exists on requirement ID "
                "'%s'" % self.cel_ids[index])

        if match_found:
            # if no order specified then we want this to pass
            if after is None and before is None:
                return
            else:
                logger.debug("Partial order found on requirement ID '%s'. "
                        "Strict ordering NOT enforced." %
                        self.cel_ids[index])
                # check before and after order
                self.check_order(index, event, match_found)
                return
        if not match_found and not submatch_found:
            if after is None and before is None:
                logger.debug("No partial order found on requirement ID "
                        "'%s'. Strict ordering enforced." %
                        self.cel_ids[index])
                self.mark_failed('partial_order', self.cel_ids[index], event)
                return
            else:
                logger.debug("Found partial order on requirement ID '%s'. "
                        "Strict ordering NOT enforce for this expected event." %
                        self.cel_ids[index])
                return
        if not match_found and submatch_found:
            if after is None and before is None:
                logger.debug("No partial order found on requirement ID "
                        "'%s'. Strict ordering enforced on this sub match." %
                        self.cel_ids[index])
                self.mark_failed('partial_order', self.cel_ids[index], event)
                return
            else:
                logger.debug("Found partial order on requirement ID '%s'. "
                        "Strict ordering NOT enforce for this expected event "
                        "sub match." % self.cel_ids[index])
                # check before and after order
                self.check_order(index, event, match_found)
                return

    def find_requirement_match(self, event):
        logger.debug("Trying to find a requirement that matches")
        submatch_found = False
        # Search from our current index+1(since we know it doesn't match our
        # current index) to the last
        for i in range(self.match_index + 1, len(self.match_requirements)):
            # Get dict from list for whatever index we are on:
            expected = self.match_requirements[i]

            hdrmatchcnt = 0
            numkeys = 0
            for k,v in expected.items():
                numkeys += 1
                if re.match(v, event.get(k)):
                    hdrmatchcnt += 1
            if hdrmatchcnt == numkeys:
                self.submatch_index = i
                submatch_found = True
                break

        if submatch_found:
            logger.debug("Found a sub requirement that matches at ID '%s'" %
                    self.cel_ids[self.submatch_index])
        else:
            self.mark_failed('nomatches', None, None, event)

        return submatch_found

    def check_order(self, index, event, match_found):
        # Check if the 'after' partial order requirement is met.
        matched_after = self.check_after_order(index)

        # Check if the 'before' partial order requirement is met.
        matched_before = self.check_before_order(index)

        if not matched_after or not matched_before:
            if match_found:
                logger.debug("A match was found at requirement ID '%s' "
                        "but the partial order requirement failed!" %
                        self.cel_ids[index])
            else:
                logger.debug("A match was found at sub requirement ID "
                        "'%s' but the partial order requirement failed!" %
                        self.cel_ids[index])
                logger.warning("Received event does *NOT* match expected "
                        "event")
            self.mark_failed('partial_order', self.cel_ids[index])

    def check_after_order(self, index):
        # Lets see if we have a 'after' partial order specified for this
        # expected event we found to match the received event.
        logger.debug("Checking the 'after' partial order requirements for expected "
                "event at requirement ID '%s'" % self.cel_ids[index])
        # We know that either 'after' or 'before' has a value since
        # check_partorder_exists() already told us that at least one of them does.
        # If 'after' is None then it's NOT a problem and therefore we set our
        # var to True.
        if self.partial_order_requirements[index].get('after') is None:
            after_range_matched = True
        else:
            after = self.partial_order_requirements[index].get('after')
            # Check the 'after' order specified on the expected event that was
            # matched to see if the expected event corresponding to the value of
            # 'after' was already matched or not.
            if after in self.matched_events:
                logger.debug("The expected match for requirement ID '%s' did "
                        "occur after the requirement ID '%s'" %
                        (self.cel_ids[index], after))
                after_range_matched = True
            else:
                logger.debug("The expected match for requirement ID '%s' did "
                        "*NOT* occur after the requirement ID '%s'" %
                        (self.cel_ids[index], after))
                after_range_matched = False

        return after_range_matched

    def check_before_order(self, index):
        logger.debug("Checking the 'before' partial order requirements for expected "
                "event at requirement ID '%s'" % self.cel_ids[index])
        # We know that either 'after' or 'before' has a value since
        # check_partorder_exists() already told us that at least one of them does.
        # If 'before' is None then it's NOT a problem and therefore we set our
        # var to True.
        if self.partial_order_requirements[index].get('before') is None:
            before_range_matched = True
        else:
            before = self.partial_order_requirements[index].get('before')
            # Check the 'before' order specified on the expected event that was
            # matched to see if the expected event corresponding to the value of
            # 'before' was already matched or not.
            if before not in self.matched_events:
                logger.debug("The expected match for requirement ID '%s' did "
                        "occur before the requirement ID '%s'" %
                        (self.cel_ids[index], before))
                before_range_matched = True
            else:
                logger.debug("The expected match for requirement ID '%s' did "
                        "*NOT* occur before the requirement ID '%s'" %
                        (self.cel_ids[index], before))
                before_range_matched = False

        return before_range_matched

    def mark_failed(self, item_failed, cel_id, expected = None, received = None):
        self.passed = False
        self.marked_failed = True
        if item_failed == "partial_order":
            logger.error("The partial order failed or doesn't exist for "
                    "requirement ID '%s'" % cel_id)
        if item_failed == "match":
            logger.error("The match failed for requirement ID '%s'" % cel_id)
            logger.error("=== Event expected ===")
            logger.error(expected)
            logger.error("=== Event received ===")
            logger.error(received)
        if item_failed == "nomatches":
            logger.error("No requirement could be matched for the received "
                    "event:")
            logger.error("%s" % received)
        if item_failed == "nokey":
            logger.error("Required CEL key '%s' not found in received "
                    "event" % expected)
            logger.error("=== Event received ===")
            logger.error(received)

        logger.debug("Marking test as failed!")
        return

    def check_result(self, callback_param):
        self.test_object.set_passed(self.passed)
        return callback_param

class AMICallbackInstance(AMIEventInstance):
    '''
    Subclass of AMIEventInstance that operates by calling a user-defined
    callback function. The callback function returns the current disposition
    of the test (i.e. whether the test is currently passing or failing).
    '''
    def __init__(self, instance_config, test_object):
        super(AMICallbackInstance, self).__init__(instance_config, test_object)
        self.callback_module = instance_config['callbackModule']
        self.callback_method = instance_config['callbackMethod']
        if 'start' in instance_config:
            self.passed = True if instance_config['start'] == 'pass' else False

    def event_callback(self, ami, event):
        callback_module = __import__(self.callback_module)
        method = getattr(callback_module, self.callback_method)
        self.passed = method(ami, event)
        if self.passed == None:
            logger.error("Callback %s.%s returned None instead of a boolean" %
                (self.callback_module, self.callback_method))
            self.passed = False

    def check_result(self, callback_param):
        self.test_object.set_passed(self.passed)
        return callback_param

class AMIEventInstanceFactory:
    @staticmethod
    def create_instance(instance_config, test_object):
        instance_type = instance_config['type']
        if instance_type == "headermatch":
            logger.debug("instance type is 'headermatch'")
            return AMIHeaderMatchInstance(instance_config, test_object)
        elif instance_type == "orderedheadermatch":
            logger.debug("instance type is 'orderedheadermatch'")
            return AMIOrderedHeaderMatchInstance(instance_config, test_object)
        elif instance_type == "cel":
            logger.debug("instance type is 'cel'")
            return AMICel(instance_config, test_object)
        elif instance_type == "callback":
            logger.debug("instance type is 'callback'")
            return AMICallbackInstance(instance_config, test_object)
        else:
            logger.error("Invalid type %s specified for AMI event instance" %
                    instance_type)
            raise Exception

class AMIEventModule(object):
    def __init__(self, module_config, test_object):
        logger.debug("Initializing AMIEvent module")
        self.test_object = test_object
        self.ami_instances = []
        for instance in module_config:
            self.ami_instances.append(AMIEventInstanceFactory.create_instance(instance,
                test_object))

class AMI:
    def __init__(self, on_login, on_error, timeout=60, user="mark", secret="mysecret", host="127.0.0.1", port=5038):
        self.on_login = on_login
        self.on_error = on_error
        self.login_timeout = timeout
        self.user = user
        self.secret = secret
        self.host = host
        self.port = port
        self.__attempts = 0
        self.__start = None
        self.ami_factory = manager.AMIFactory(self.user, self.secret)

    def login(self):
        self.__attempts = self.__attempts + 1
        logger.debug("AMI Login attempt #%d" % (self.__attempts))
        if not self.__start:
            self.__start = datetime.datetime.now()
        self.ami_factory.login(self.host, self.port).addCallbacks(self.on_login_success, self.on_login_error)

    def on_login_success(self, ami):
        self.ami = ami
        logger.debug("AMI Login succesful")
        return self.on_login(ami)

    def on_login_error(self, reason):
        runtime = (datetime.datetime.now() - self.__start).seconds
        if runtime >= self.login_timeout:
            logger.error("AMI login failed after %d second timeout" % (self.login_timeout))
            return self.on_error()
        delay = 2 ** self.__attempts
        if delay + runtime >= self.login_timeout:
            delay = self.login_timeout - runtime
        reactor.callLater(delay, self.login)

