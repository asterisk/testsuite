'''
Copyright (C) 2014, Digium, Inc.
Joshua Colp <jcolp@digium.com>

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

    return True


def on_recording_started(ari, event, test_object):
    LOGGER.info("Recording started")

    if event['recording']['name'] != 'superfly':
        LOGGER.error('Recording start event does not contain correct name')
        fail_test()
        return
    elif event['recording']['format'] != 'wav':
        LOGGER.error('Recording start event does not contain correct format')
        fail_test()
        return
    elif event['recording']['target_uri'] != 'channel:' + TEST.channel_id:
        LOGGER.error('Recording start event does not contain correct target URI')
        fail_test()
        return
    elif event['recording']['state'] != 'recording':
        LOGGER.error('Recording start event does not contain correct state')
        fail_test()
        return

    LOGGER.info("Now stopping recording")

    try:
        TEST.ari.post('recordings/live', 'superfly', 'stop')
    except requests.exceptions.HTTPError:
        LOGGER.error('Failed to stop recording.')
        fail_test()
        return

    LOGGER.info("Recording stopped successfully. Leave Stasis.")
    try:
        TEST.ari.post('channels', TEST.channel_id, 'continue')
    except requests.exceptions.HTTPError:
        LOGGER.error('Failed to leave stasis. Crud.')
        fail_test()
        return

    LOGGER.info("All tests complete: The channel should be out of stasis.")

    return True


def on_recording_finished(ari, event, test_object):
    LOGGER.info("Recording finished")

    if event['recording']['name'] != 'superfly':
        LOGGER.error('Recording start event does not contain correct name')
        fail_test()
        return
    elif event['recording']['format'] != 'wav':
        LOGGER.error('Recording start event does not contain correct format')
        fail_test()
        return
    elif event['recording']['target_uri'] != 'channel:' + TEST.channel_id:
        LOGGER.error('Recording start event does not contain correct target URI')
        fail_test()
        return
    elif event['recording']['state'] != 'done':
        LOGGER.error('Recording start event does not contain correct state')
        fail_test()
        return

    return True
