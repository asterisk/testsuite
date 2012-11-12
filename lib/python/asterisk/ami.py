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
        self.passed = True
        self._registered = False

        if 'count' in instance_config:
            count = instance_config['count']
            if count[0] == '<':
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
        self.match_requirements = (
                instance_config['requirements'].get('match', {}))
        self.nonmatch_requirements = (
                instance_config['requirements'].get('nomatch', {}))

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

