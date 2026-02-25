"""
Copyright (C) 2026, Aurora Innovation AB

This program is free software, distributed under the terms of
the GNU General Public License Version 2.

StasisBroadcast app_filter test.

Two ARI apps are registered: 'ivr-main' and 'support'.  The dialplan
invokes StasisBroadcast with app_filter=^ivr-.*, so only 'ivr-main'
should receive the CallBroadcast event.

The count: 1 constraint on CallBroadcast in the YAML acts as the filter
verification — a second delivery (to 'support') would increment the count
to 2 and cause the test to fail at teardown.
"""

import logging

LOGGER = logging.getLogger(__name__)


def on_broadcast(ari, event, test_object):
    """Claim the channel on behalf of 'ivr-main', asserting it is the recipient."""
    channel_id = event['channel']['id']
    application = event.get('application', '')
    LOGGER.info("CallBroadcast for app '%s', channel %s", application, channel_id)

    if application != 'ivr-main':
        LOGGER.error("Expected CallBroadcast for 'ivr-main'; received for '%s'",
                     application)
        test_object.set_passed(False)
        return False

    ari.set_allow_errors(True)
    resp = ari.post('events', 'claim',
                    channelId=channel_id, application='ivr-main')

    if resp.status_code != 204:
        LOGGER.error("Expected HTTP 204 from claim, got %d: %s",
                     resp.status_code, resp.text)
        test_object.set_passed(False)
        return False

    LOGGER.info("Channel %s claimed by 'ivr-main'", channel_id)
    return True


def on_stasis_start(ari, event, test_object):
    """Verify the channel entered the correct Stasis app and clean up."""
    channel_id = event['channel']['id']
    application = event.get('application', '')
    LOGGER.info("StasisStart for channel %s in app '%s'", channel_id, application)

    if application != 'ivr-main':
        LOGGER.error("Expected StasisStart in 'ivr-main', got '%s'", application)
        test_object.set_passed(False)
        return False

    ari.delete('channels', channel_id)
    return True
