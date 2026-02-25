"""
Copyright (C) 2026, Aurora Innovation AB

This program is free software, distributed under the terms of
the GNU General Public License Version 2.

StasisBroadcast timeout test.

A channel enters StasisBroadcast with a short timeout.  No ARI application
claims the channel.  After the timeout expires the dialplan emits a
UserEvent(BroadcastStatus, Status:TIMEOUT).  This module verifies that the
UserEvent carries the expected value and then stops the reactor.
"""

import logging

LOGGER = logging.getLogger(__name__)


class TimeoutTest(object):
    """Pluggable module that verifies STASISSTATUS=TIMEOUT via AMI UserEvent."""

    def __init__(self, module_config, test_object):
        self.test_object = test_object
        test_object.register_ami_observer(self.on_ami_connect)

    def on_ami_connect(self, ami):
        """Called when AMI connects; register for UserEvent notifications."""
        if ami.id != 0:
            return
        ami.registerEvent('UserEvent', self.on_user_event)

    def on_user_event(self, ami, event):
        """Verify the BroadcastStatus UserEvent contains Status=TIMEOUT."""
        if event.get('userevent') != 'BroadcastStatus':
            return

        status = event.get('status', '')
        LOGGER.info("BroadcastStatus UserEvent received: Status=%s", status)

        if status != 'TIMEOUT':
            LOGGER.error("Expected STASISSTATUS=TIMEOUT, got '%s'", status)
            self.test_object.set_passed(False)

        self.test_object.stop_reactor()
