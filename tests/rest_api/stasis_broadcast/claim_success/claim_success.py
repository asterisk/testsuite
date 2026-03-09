"""
Copyright (C) 2026, Aurora Innovation AB

This program is free software, distributed under the terms of
the GNU General Public License Version 2.

Nominal StasisBroadcast claim test.

A channel enters StasisBroadcast via dialplan.  The 'testsuite' ARI
application receives a CallBroadcast event, claims the channel via
POST /events/claim, and expects the channel to appear in StasisStart.
"""

import logging

LOGGER = logging.getLogger(__name__)


def on_broadcast(ari, event, test_object):
    """Handle the CallBroadcast event and claim the channel."""
    channel_id = event['channel']['id']
    application = event.get('application', '')
    LOGGER.info("CallBroadcast for app '%s', channel %s", application, channel_id)

    # Allow non-2xx responses so we can inspect the status code ourselves
    # (the ARI helper raises by default, and 204 triggers a spurious log
    # entry due to integer vs. float division in Python 3).
    ari.set_allow_errors(True)
    resp = ari.post('events', 'claim',
                    channelId=channel_id, application='testsuite')

    if resp.status_code != 204:
        LOGGER.error("Expected HTTP 204 from claim, got %d: %s",
                     resp.status_code, resp.text)
        test_object.set_passed(False)
        return False

    LOGGER.info("Channel %s claimed successfully", channel_id)
    return True


def on_stasis_start(ari, event, test_object):
    """Handle StasisStart for the claimed channel and clean up."""
    channel_id = event['channel']['id']
    application = event.get('application', '')
    LOGGER.info("StasisStart for channel %s in app '%s'", channel_id, application)

    if application != 'testsuite':
        LOGGER.error("Expected StasisStart in 'testsuite', got '%s'", application)
        test_object.set_passed(False)
        return False

    ari.delete('channels', channel_id)
    return True
