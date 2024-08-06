"""Test drivers for the func_tonedetect test"""

import logging
import json
import time

LOGGER = logging.getLogger(__name__)

PLAYBACK_CHAN = None
TEST_CHAN = None
FINAL_PLAYBACK = None

def check_playback(ari, event, test_object):
    """Handler for the PlaybackFinished event

    When the last sound file has played back, release the testing channel back
    into the dialplan to continue the test.

    Keyword Arguments:
    ari         Our ARI client
    event       The StasisStart event for the application
    test_object The test object for this test
    """

    if event['playback']['id'] == FINAL_PLAYBACK:
        ari.post("channels", TEST_CHAN, "continue")

    return True

def on_start(ari, event, test_object):
    """Gather our Local channel halves, set up subscriptions, and start testing

    This is the entry point for the Stasis application that the Local channel
    is originated into. Both halves enter - the ;1 is released into the
    dialplan to run the tests, while the ;2 is used to play audio back. The
    audio is considered on the 'read' side of the ;1 channel, and drives each
    individual test (see do_playback).

    Keyword Arguments:
    ari         Our ARI client
    event       The StasisStart event for the application
    test_object The test object for this test
    """
    global PLAYBACK_CHAN
    global TEST_CHAN

    args = event.get('args')

    channel_name = event["channel"]["name"]
    channel_id = event["channel"]["id"]
    if ";1" in channel_name:
        TEST_CHAN = channel_id

        ari.post("applications", "testsuite", "subscription",
                 eventSource="channel:%s" % channel_id)
    else:
        PLAYBACK_CHAN = channel_id

    if TEST_CHAN and PLAYBACK_CHAN:
        ari.post("channels", TEST_CHAN, "continue",
                 context="default",
                 extension="test",
                 priority=1)

    return True

def do_playback(ari, event, test_object):
    """Entry point for a Stasis application that plays back
    a ring (440 Hz) tone.

    Keyword Arguments:
    ari         Our ARI client
    event       The StasisStart event for the application
    test_object The test object for this test
    """
    global FINAL_PLAYBACK

    test_object.reset_timeout()

    if not PLAYBACK_CHAN:
        LOGGER.error("No playback channel for Stasis playback app")
        test_object.set_passed(False)
        return False

    playback = ari.post("channels", PLAYBACK_CHAN, "play",
             media="tone:ring;tonezone=fr")

    json_response = json.loads(playback.content)
    FINAL_PLAYBACK = json_response.get('id')

    time.sleep(1)

    ari.delete("playbacks", FINAL_PLAYBACK)


    return True


