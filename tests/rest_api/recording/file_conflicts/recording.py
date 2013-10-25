'''
Copyright (C) 2013, Digium, Inc.
Jonathan Rose <jrose@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
'''

import logging
import requests
from twisted.internet import reactor

LOGGER = logging.getLogger(__name__)


class TestLogic(object):
    def __init__(self):
        self.channel_id = None

TEST = TestLogic()


def fail_test():
    TEST.test_object.set_passed(False)
    TEST.test_object.stop_reactor()


def on_start(ari, event, test_object):
    TEST.test_object = test_object
    TEST.ari = ari

    LOGGER.debug("on_start(%r)" % event)
    TEST.channel_id = event['channel']['id']

    LOGGER.info("Channel '%s' connected to Stasis. Starting the test")
    LOGGER.info("Attempting to answer the channel.")

    try:
        TEST.ari.post('channels', TEST.channel_id, 'answer')
    except requests.exceptions.HTTPError:
        LOGGER.error('Failed to answer.')
        fail_test()
        return True

    LOGGER.info("Answered the channel. Starting the baseline recording.")

    try:
        TEST.ari.post('channels', TEST.channel_id, 'record',
                      name="superfly", format="wav")
    except requests.exceptions.HTTPError:
        LOGGER.error("Failed to record.")
        fail_test()
        return True

    LOGGER.info("Baseline recording started successfully.")

    # XXX No recording started events yet, so we allow time before continuing.
    reactor.callLater(0.2, step_two)
    return True


def step_two():
    LOGGER.info("Attempting to stop the baseline recording.")

    try:
        TEST.ari.post('recordings/live', 'superfly', 'stop')
    except requests.exceptions.HTTPError:
        LOGGER.error('Failed to stop recording.')
        fail_test()
        return

    LOGGER.info("Baseline recording stopped.")
    LOGGER.info("Attempting to start expected failure recording: "
                "(file name conflict).")

    try:
        # Overwrite is not allowed and the file will already exist,
        # so this should fail.
        TEST.ari.post('channels', TEST.channel_id, 'record',
                      name="superfly", format="wav",
                      ifExists="fail")
        LOGGER.error('This recording was supposed to fail and it did not.')
        fail_test()
        return
    except requests.exceptions.HTTPError:
        pass

    LOGGER.info("The recording failed as expected.")
    LOGGER.info("Attempting to start recording with overwrite enabled")

    try:
        # Overwrite is allowed, so recording should succeed this time.
        TEST.ari.post('channels', TEST.channel_id, 'record',
                      name="superfly", format="wav",
                      ifExists="overwrite")
    except requests.exceptions.HTTPError:
        LOGGER.error('Failed to record in overwrite mode.')
        fail_test()
        return

    LOGGER.info("The overwrite recording started successfully")

    # XXX No recording started events yet, so we allow time before continuing.
    reactor.callLater(0.2, step_three)


def step_three():
    LOGGER.info("Attempting to stop the overwrite recording")

    try:
        TEST.ari.post('recordings/live', 'superfly', 'stop')
    except requests.exceptions.HTTPError:
        LOGGER.error('Failed to stop overwrite recording.')
        fail_test()
        return

    LOGGER.info("Overwrite recording stopped successfully. Leave Stasis.")

    try:
        TEST.ari.post('channels', TEST.channel_id, 'continue')
    except requests.exceptions.HTTPError:
        LOGGER.error('Failed to leave stasis. Crud.')
        fail_test()
        return

    LOGGER.info("All tests complete: The channel should be out of stasis.")
