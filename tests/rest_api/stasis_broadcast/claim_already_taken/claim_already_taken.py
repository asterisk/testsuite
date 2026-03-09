"""
Copyright (C) 2026, Aurora Innovation AB

This program is free software, distributed under the terms of
the GNU General Public License Version 2.

StasisBroadcast duplicate-claim (409) test.

Two ARI apps ('app-one' and 'app-two') are both registered.  Both receive
a CallBroadcast event.  The first claim attempt succeeds (HTTP 204); the
second must be rejected with HTTP 409 Conflict.  The winning app is
verified via StasisStart.
"""

import logging

LOGGER = logging.getLogger(__name__)


class _State(object):
    success_app = None
    conflict_app = None


STATE = _State()


def on_broadcast(ari, event, test_object):
    """Attempt to claim the channel; record 204 success or 409 conflict."""
    channel_id = event['channel']['id']
    application = event.get('application', '')
    LOGGER.info("CallBroadcast for app '%s', channel %s", application, channel_id)

    # Allow non-2xx so we can inspect the status code rather than catching
    # an HTTPError raised by the default ari.post() error handling.
    ari.set_allow_errors(True)
    resp = ari.post('events', 'claim',
                    channelId=channel_id, application=application)
    status = resp.status_code

    LOGGER.info("Claim by '%s': HTTP %d", application, status)

    if status == 204:
        if STATE.success_app is not None:
            LOGGER.error("More than one claim succeeded (first: '%s', now: '%s')",
                         STATE.success_app, application)
            test_object.set_passed(False)
            return False
        STATE.success_app = application
    elif status == 409:
        if STATE.conflict_app is not None:
            LOGGER.error("More than one claim got 409 (first: '%s', now: '%s')",
                         STATE.conflict_app, application)
            test_object.set_passed(False)
            return False
        STATE.conflict_app = application
    else:
        LOGGER.error("Unexpected HTTP %d from claim by '%s'", status, application)
        test_object.set_passed(False)
        return False

    return True


def on_stasis_start(ari, event, test_object):
    """Verify the winner app received StasisStart and clean up."""
    channel_id = event['channel']['id']
    application = event.get('application', '')
    LOGGER.info("StasisStart for channel %s in app '%s'", channel_id, application)

    if STATE.success_app is not None and application != STATE.success_app:
        LOGGER.error("StasisStart arrived in '%s' but winning app was '%s'",
                     application, STATE.success_app)
        test_object.set_passed(False)
        return False

    ari.delete('channels', channel_id)
    return True
