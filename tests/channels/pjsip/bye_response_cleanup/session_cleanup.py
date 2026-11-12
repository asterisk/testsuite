"""Check BYE session destruction before Asterisk shuts down."""

import logging

from twisted.internet import reactor


LOGGER = logging.getLogger(__name__)


class SessionCleanup:
    """Require one destruction event per successful SIPp call."""

    def __init__(self, module_config, test_object):
        self.test_object = test_object
        self.ami = None
        self.destroyed = set()
        self.scenarios_finished = False
        self.deadlines = {}
        self.endpoints = {'bye-200', 'bye-408', 'bye-481'}
        self.token = test_object.create_fail_token(
            'Sessions were not destroyed before Asterisk shutdown')
        test_object.register_ami_observer(self.ami_connect)
        test_object.register_scenario_started_observer(self.scenario_started)
        test_object.register_scenario_stopped_observer(self.scenario_stopped)
        test_object.register_final_observer(self.scenarios_complete)

    def ami_connect(self, ami):
        """Listen before originating any calls."""
        self.ami = ami
        ami.registerEvent('TestEvent', self.test_event)

    def scenario_started(self, scenario):
        """Originate after the corresponding SIPp listener has started."""
        self.ami.originate(
            channel='PJSIP/' + scenario.scenario['-s'],
            context='default', exten='hangup', priority=1, nowait=True,
        ).addErrback(self.originate_failed)

    def originate_failed(self, reason):
        """Fail if AMI rejects an originate action."""
        LOGGER.error('Originate failed: %s', reason.getErrorMessage())
        self.test_object.set_passed(False)
        self.test_object.stop_reactor()

    def test_event(self, ami, event):
        """Ignore destruction caused by test teardown."""
        if self.test_object._stopping:
            return
        endpoint = event.get('endpoint')
        if (event.get('state') != 'SESSION_DESTROYING'
                or endpoint not in self.endpoints):
            return
        if endpoint in self.destroyed:
            LOGGER.error('Duplicate SESSION_DESTROYING for %s', endpoint)
            self.test_object.set_passed(False)
            self.test_object.stop_reactor()
            return
        LOGGER.info('SESSION_DESTROYING for %s before shutdown', endpoint)
        self.destroyed.add(endpoint)
        deadline = self.deadlines.pop(endpoint, None)
        if deadline is not None and deadline.active():
            deadline.cancel()
        self.check_complete()

    def scenario_stopped(self, scenario):
        """Bound cleanup after this call's final response was sent."""
        if self.test_object._stopping or not scenario.passed:
            return
        endpoint = scenario.scenario['-s']
        if endpoint not in self.destroyed:
            self.deadlines[endpoint] = reactor.callLater(
                5.5, self.cleanup_timeout)

    def scenarios_complete(self, iteration, test_object):
        """Require all SIPp calls to complete before accepting destruction."""
        if self.test_object._stopping:
            return
        self.scenarios_finished = True
        self.check_complete()

    def check_complete(self):
        """Only remove the failure token while Asterisk is still running."""
        if not self.scenarios_finished or self.destroyed != self.endpoints:
            return
        self.test_object.remove_fail_token(self.token)
        self.test_object.set_passed(True)
        self.test_object.stop_reactor()

    def cleanup_timeout(self):
        """Freeze failure before shutdown can release retained sessions."""
        if self.test_object._stopping:
            return
        LOGGER.error('Missing SESSION_DESTROYING before shutdown: %s',
                     sorted(self.endpoints - self.destroyed))
        self.test_object.set_passed(False)
        self.test_object.stop_reactor()
