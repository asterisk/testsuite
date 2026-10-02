"""
Test that Asterisk fires ChannelMessageReceived when an in-dialog SIP MESSAGE
is received on a Stasis channel.
"""

import logging

from asterisk.sipp import SIPpScenario
from twisted.internet import reactor

LOGGER = logging.getLogger(__name__)


class RecvInDialogMessage(object):
    """Wait for ChannelMessageReceived on an active Stasis channel."""

    def __init__(self, module_config, test_object):
        self.config = module_config
        self.test_object = test_object
        self.channel_id = None
        self.event_received = False

        self.test_object.register_ami_observer(self._on_ami_connection)
        self.test_object.register_ws_event_handler(self._on_ws_event)
        self.test_object.register_stop_observer(self._on_stop)

    def _on_ami_connection(self, ami):
        if ami.id != 0:
            return
        for scenario_def in self.config.get('sipp', []):
            scenario = SIPpScenario(self.test_object.test_name, scenario_def)
            scenario.run(self.test_object)

    def _on_ws_event(self, event):
        event_type = event.get('type')

        if event_type == 'StasisStart':
            self.channel_id = event.get('channel', {}).get('id')
            LOGGER.debug("Stasis channel up: %s", self.channel_id)
            return

        if event_type == 'ChannelMessageReceived':
            msg = event
            channel = event.get('channel')
            LOGGER.debug("ChannelMessageReceived: channel=%s body=%r",
                         channel, event.get('body'))

            expected = self.config.get('expected', {})
            for key, val in expected.items():
                if msg.get(key) != val:
                    LOGGER.error("ChannelMessageReceived field %s: expected %r got %r",
                                 key, val, msg.get(key))
                    self.test_object.set_passed(False)

            if channel is None:
                LOGGER.error("ChannelMessageReceived has no channel field")
                self.test_object.set_passed(False)
            elif channel.get('id') != self.channel_id:
                LOGGER.error("ChannelMessageReceived channel %s != stasis channel %s",
                             channel.get('id'), self.channel_id)
                self.test_object.set_passed(False)

            self.event_received = True
            self._cleanup()

    def _cleanup(self):
        if self.channel_id:
            self.test_object.ari.set_allow_errors(True)
            self.test_object.ari.delete('channels', self.channel_id)
            self.test_object.ari.set_allow_errors(False)
        reactor.callLater(1.0, self.test_object.stop_reactor)

    def _on_stop(self, *args):
        if not self.event_received:
            LOGGER.error("No ChannelMessageReceived event for in-dialog MESSAGE")
            self.test_object.set_passed(False)
        elif self.test_object.passed is not False:
            self.test_object.set_passed(True)
