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
        self.step = 'baseline'


TEST = TestLogic()


def fail_test(msg):
    LOGGER.error(msg)
    TEST.test_object.set_passed(False)
    TEST.test_object.stop_reactor()
    return True


def on_start(ari, event, test_object):
    TEST.test_object = test_object

    LOGGER.debug("on_start(%r)" % event)
    TEST.channel_id = event['channel']['id']

    LOGGER.info("Channel '%s' connected to Stasis. Starting the test")
    LOGGER.info("Attempting to answer the channel.")

    try:
        ari.post('channels', TEST.channel_id, 'answer')
    except requests.exceptions.HTTPError:
        return fail_test('Failed to answer.')

    LOGGER.info("Answered the channel. Starting the baseline recording.")

    try:
        ari.post('channels', TEST.channel_id, 'record',
                      name="superfly", format="wav")
    except requests.exceptions.HTTPError:
        return fail_test("Failed to record.")

    return True


def on_recording_started(ari, event, test_object):
    LOGGER.info("{0} recording started successfully".format(TEST.step))
    LOGGER.info("Attempting to stop the {0} recording.".format(TEST.step))

    try:
        ari.post('recordings/live', 'superfly', 'stop')
    except requests.exceptions.HTTPError:
        return fail_test('Failed to stop {0} recording.'.format(TEST.step))

    return True


def on_recording_finished(ari, event, test_object):
    LOGGER.info("{0} recording stopped successfully.".format(TEST.step))

    if TEST.step == 'overwrite':
        # Once done with the overwrite recording end the test
        LOGGER.info("Time to leave stasis.")

        try:
            ari.post('channels', TEST.channel_id, 'continue')
        except requests.exceptions.HTTPError:
            return fail_test('Failed to leave stasis.')

        LOGGER.info("Tests completed: The channel should be out of stasis.")
        return True

    # Baseline recording done, so attempt overwrite tests
    TEST.step = 'overwrite'
    LOGGER.info("First overwrite attempt (expecting failure).")

    try:
        # Overwrite is not allowed and the file will already exist,
        # so this should fail.
        ari.post('channels', TEST.channel_id, 'record', name="superfly",
                      format="wav", ifExists="fail")
        return fail_test('First overwrite attempt did not fail.')
    except requests.exceptions.HTTPError:
        pass

    LOGGER.info("Second overwrite attempt (expecting success).")

    try:
        # Overwrite is allowed, so recording should succeed this time.
        ari.post('channels', TEST.channel_id, 'record', name="superfly",
                      format="wav", ifExists="overwrite")
    except requests.exceptions.HTTPError:
        return fail_test('Failed to record in overwrite mode.')

    return True
