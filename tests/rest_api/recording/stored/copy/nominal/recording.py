"""
Copyright (C) 2014, Digium, Inc.
Joshua Colp <jcolp@digium.com>
Matt Jordan <mjordan@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
"""

import logging
import requests
from twisted.internet import reactor

LOGGER = logging.getLogger(__name__)

class TestLogic(object):
    """A small object used to hold test data between events"""

    def __init__(self):
        """Constructor"""
        self.channel_id = None
        self.test_object = None
        self.ari = None

TEST = TestLogic()


def fail_test():
    """Fail the running test
    """
    TEST.test_object.set_passed(False)
    TEST.test_object.stop_reactor()


def on_start(ari, event, test_object):
    """Handle StasisStart event

    This will kick off a recording of superfly

    Keyword Arguments:
    event The StasisStart event
    test_object Our one and only test object
    """
    TEST.test_object = test_object
    TEST.ari = ari

    TEST.channel_id = event['channel']['id']

    LOGGER.info("Channel '%s' connected to Stasis. Starting the test")
    TEST.ari.post('channels', TEST.channel_id, 'answer')
    try:
        TEST.ari.post('channels', TEST.channel_id, 'record',
                      name="superfly", format="wav")
    except requests.exceptions.HTTPError:
        LOGGER.error("Failed to record.")
        fail_test()
        return
    LOGGER.info("Baseline recording started successfully.")
    return True

def on_recording_started(ari, event, test_object):
    """Handler for the RecordingStarted event

    This will stop the recording after 2 seconds

    Keyword Arguments:
    event The RecordingStarted event
    test_object Our one and only test object
    """
    LOGGER.info("Recording started")

    def _stop_recording(ari):
        """Stop the live recording

        Keyword Arguments:
        ari The ARI object, passed in as a convenience
        """
        LOGGER.info("Now stopping recording")
        try:
            ari.post('recordings/live', 'superfly', 'stop')
        except requests.exceptions.HTTPError:
            LOGGER.error('Failed to stop recording.')
            fail_test()
            return True

    reactor.callLater(2, _stop_recording, TEST.ari)
    return True

def on_recording_finished(ari, event, test_object):
    """Handler for the RecordingFinished

    Verify we have superfly as a stored recording, then
    make a copy of it as superfreak in a subfolder 'copy'

    Keyword Arguments:
    event The RecordingFinished event
    test_object Our one and only test object
    """
    LOGGER.info("Recording finished")

    try:
        stored = TEST.ari.get('recordings/stored', 'superfly').json()
    except requests.exceptions.HTTPError:
        LOGGER.error('Failed to get stored recording of superfly')
        fail_test()
        return

    if stored['name'] != 'superfly':
        LOGGER.error('Stored recording of superfly has incorrect name')
        fail_test()
        return
    elif stored['format'] != 'wav':
        LOGGER.error('Stored recording of superfly has incorrect format')
        fail_test()
        return

    try:
        superfreak = TEST.ari.post('recordings/stored', 'superfly', 'copy',
            destinationRecordingName='copy/superfreak').json()
    except requests.exceptions.HTTPError:
        LOGGER.error('Failed to get copied recording superfreak')
        fail_test()

    if superfreak['name'] != 'copy/superfreak':
        LOGGER.error('Stored recording of superfreak has incorrect name')
        fail_test()
        return
    elif superfreak['format'] != 'wav':
        LOGGER.error('Stored recording of superfreak has incorrect format')
        fail_test()
        return

    LOGGER.info("Recording stopped and copied successfully. Leave Stasis.")
    try:
        TEST.ari.post('channels', TEST.channel_id, 'continue')
    except requests.exceptions.HTTPError:
        LOGGER.error('Failed to leave stasis. Crud.')
        fail_test()
        return
    return True


def on_stasis_end(ari, event, test_object):
    """Handler for StasisEnd

    End the test

    Keyword Arguments:
    event The StasisEnd event
    test_object Our one and only test object
    """
    LOGGER.info("Test finished")
    test_object.stop_reactor()
    return True

