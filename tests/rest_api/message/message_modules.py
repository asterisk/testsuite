#!/usr/bin/env python
"""
Copyright (C) 2014, Digium, Inc.
Matt Jordan <mjordan@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
"""

import logging
import json
import requests

from twisted.internet import defer

from asterisk.sipp import SIPpScenario

LOGGER = logging.getLogger(__name__)


class MessageCoordinator(object):
    """Coordinater for sending/receiving messages

    Because other modules will want to do things once we're subscribed, this
    class acts as a singleton (ew) that allows pluggable modules to be
    notified once subscriptions are done.
    """

    _singleton_instance = None

    @staticmethod
    def get_instance():
        """Return the singleton instance of the message coordinator"""
        if (MessageCoordinator._singleton_instance is None):
            # Note that the constructor sets the singleton instance.
            # This is a tad backwards, but is needed for the pluggable
            # framework.
            MessageCoordinator._singleton_instance = MessageCoordinator()
        return MessageCoordinator._singleton_instance

    def __init__(self):
        """Constructor"""

        self._observers = []

    def register_observer(self, observer):
        """Register a callback function to be called when we get poked

        The callback function takes no arguments. It just gets poked.
        """
        self._observers.append(observer)

    def poke_observers(self):
        """Let the observers know that something happened"""
        for observer in self._observers:
            LOGGER.info('Poking observer...')
            observer()


class MessageSubscriber(object):
    """Pluggable module that makes subscriptions to the specified resources"""

    def __init__(self, module_config, test_object):
        """Constructor

        Keyword Arguments:
        module_config This object's configuration
        test_object   The one and only test object
        """
        super(MessageSubscriber, self).__init__()

        self.module_config = module_config
        self.test_object = test_object

        self.test_object.register_ami_observer(self._handle_ami_connection)

    def _handle_ami_connection(self, ami):
        """Called when the AMI connection is made

        Keyword Arguments:
        ami  Our AMI protocol wrapper
        """

        ari = self.test_object.ari
        for sub in self.module_config.get('subscriptions'):
            app = sub.get('app', 'testsuite')
            expected_response = sub.get('expected-response')
            if expected_response:
                ari.set_allow_errors(True)

            resp = ari.post("applications", app, "subscription",
                            eventSource="%s" % sub['event-source'])

            if expected_response:
                if resp.status_code != expected_response:
                    LOGGER.error('Failed to get expected response %d: Got %d' %
                                 (expected_response, resp.status_code))
                    self.test_object.set_passed(False)
                else:
                    LOGGER.info('Got expected response %d for sub to %s' %
                                (expected_response, sub['event-source']))
                    self.test_object.set_passed(True)
            ari.set_allow_errors(False)

        coordinator = MessageCoordinator.get_instance()
        coordinator.poke_observers()


class MessageSender(object):
    """Pluggable module that posts a message"""

    def __init__(self, module_config, test_object):
        """Constructor

        Keyword Arguments:
        module_config This object's configuration
        test_object   The one and only test object
        """
        super(MessageSender, self).__init__()

        self.module_config = module_config
        self.test_object = test_object

        coordinator = MessageCoordinator.get_instance()
        coordinator.register_observer(self._on_poke)

    def _on_poke(self):
        """Called when the message coordinator gets poked"""

        ari = self.test_object.ari
        for message in self.module_config.get('messages'):
            tech = message.get('tech')
            resource = message.get('resource')
            args = []

            if tech:
                args.append(tech)
            if resource:
                args.append(resource)
            args.append('sendMessage')
            url = ari.build_url('endpoints', *args)

            data = None
            headers = None
            params = message.get('params')
            if 'variables' in message:
                data = json.dumps({'variables': message['variables']})
                headers = {'Content-Type': 'application/json'}

            LOGGER.info('PUT %s %s %s' %
                        (url, params, data if data else ""))
            resp = requests.put(url, params=params, data=data,
                                headers=headers, auth=ari.userpass)


class SIPMessageRunner(object):
    """Start up a SIPp scenario for messaging purposes"""

    def __init__(self, module_config, test_object):
        """Constructor

        Keyword Arguments:
        module_config This object's configuration
        test_object   The one and only test object
        """
        super(SIPMessageRunner, self).__init__()

        self.result = []
        self.module_config = module_config
        self.test_object = test_object

        self.scenarios = []

        test_object.register_ami_observer(self._handle_ami_connection)
        test_object.register_stop_observer(self._handle_stop)

    def _handle_stop(self, result):
        """Deferred called when the reactor/test is stopped

        Keyword Arguments:
        result The object getting passed down the deferred chain
        """
        if len(self.scenarios):
            LOGGER.error("We still have %d SIPp scenarios running!" %
                         len(self.scenarios))
            self.test_object.set_passed(False)
        for scenario in self.scenarios:
            try:
                scenario.kill()
            except:
                # Move along now...
                pass

    def _handle_ami_connection(self, ami):
        """Called when the AMI connection is made

        Keyword Arguments:
        ami  Our AMI protocol wrapper
        """

        def _check_result(scenario):
            """Append the result of the test to our list of results"""
            self.scenarios.remove(scenario)
            return scenario

        def _set_pass_fail(result):
            """Check if all tests have passed

            If any have failed, set our passed status to False"""
            passed = all(r[0] for r in result)
            self.test_object.set_passed(passed)

            if (self.module_config.get('end-on-success', False) and passed):
                self.test_object.stop_reactor()
            return result

        deferds = []
        for scenario_def in self.module_config.get('sipp'):
            scenario = SIPpScenario(self.test_object.test_name, scenario_def)

            deferred = scenario.run(self.test_object)
            deferred.addCallback(_check_result)
            deferds.append(deferred)

            self.scenarios.append(scenario)

        defer.DeferredList(deferds).addCallback(_set_pass_fail)
