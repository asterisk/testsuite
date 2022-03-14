#!/usr/bin/env python
'''
Copyright (C) 2016, Digium, Inc.
Kevin Harwell <kharwell@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
'''

import os
import sys
import logging
from twisted.internet import reactor

from asterisk import ari
import tonetest

sys.path.append("lib/python")

LOGGER = logging.getLogger(__name__)


def _get_media(test_object):
    """Retrieve the media to playback from the given test object.

    :param test_object The test object
    """

    def __get_playback_file():
        duration = 0
        for t in test_object.tones:
            duration += t['duration']
        return ('sound:' + os.getcwd() + '/' + test_object.test_name + '/' +
                test_object.playback_file, duration / 1000)

    def __get_tones():
        tones = ""
        duration = 0
        for t in test_object.tones:
            tones += str(t['frequency']) + '/' + str(t['duration']) + ','
            duration += t['duration']
        return ('tone:' + tones.rstrip(','), duration / 1000)

    return __get_playback_file() if test_object.playback_file else __get_tones()


def on_start(ari, event, test_object):
    """Handle StasisStart event

    Start playback of a tone on the channel

    :param event The StasisStart event
    :param test_object The test object
    """

    def __stop_media():
        # Should be done so hangup the channel and stop the test
        ari.delete('channels', test_object.channel_id)

    test_object.channel_id = event['channel']['id']
    media, duration = _get_media(test_object)

    ari.post('channels', test_object.channel_id, 'answer')
    try:
        ari.post('channels', test_object.channel_id, 'play/play_id',
                 media=media)
    except:
        LOGGER.error("Failed to play media " + media)
        return False

    LOGGER.info("Generating {0} second(s) of media {1}"
                .format(duration, media))
    reactor.callLater(duration, __stop_media)
    return True


def on_stasis_end(ari, event, test_object):
    """Handle StasisEnd event

    Check the output file against the generated tone(s).

    :param event The StasisEnd event
    :param test_object the test object
    """

    def __validate_output(output_file, tones):
        output = tonetest.tonetest(output_file)
        if len(tones) != len(output):
            LOGGER.error("Number of generated tones {0} does not "
                         "match output {1}".format(tones, output))
            return False

        for i in range(0, len(tones)):
            LOGGER.info("Checking tone {0} against output {1}".
                        format(tones[i], output[i]))
            # Make sure the duration of the tone is within a second
            duration = tones[i]['duration'] / 1000
            if (duration < output[i]['duration'] - 1 or
                    duration > output[i]['duration'] + 1):
                LOGGER.error("Tone #{0} {1} duration out of range for {2}".
                             format(i, tones[i], output[i]))
                return False
            # Make sure the frequency of the tone is within +-7
            frequency = tones[i]['frequency']
            if (frequency < output[i]['frequency'] - 7 or
                    frequency > output[i]['frequency'] + 7):
                LOGGER.error("Tone #{0} {1} frequency out of range for {2}".
                             format(i, tones[i], output[i]))
                return False
        return True

    test_object.set_passed(__validate_output(
        test_object.sounds_path + test_object.output_file,
        test_object.tones))
    return True


class Analyzer(ari.AriTestObject):
    """Test object used to playback, record, and analyze output audio.

    Upon start of the test a channel (default - PJSIP/audio) is originated into
    the Record application with another channel entering stasis. Once in stasis,
    an audio tone (file or generated tone) is played on the channel while being
    recorded on the other channel. When play back has completed the channel
    leaves stasis and the recorded audio is checked against the configured
    tones.

    Configuration options:

    output-file: name of the file audio is recorded into (default -
        output_audio). The named file can be found in the 'sounds' directory.

    playback-file: tone file used during media playback (default - None).
        If specified, the file is expected to be under the test directory.

    tones: frequency and duration of tones found in the recorded file
        (default - 2 seconds of silence, 4 seconds of audio, 2 seconds
        of silence). Note if no playback file is specified then the given
        tones are used for playback.
    """

    on_stasis_start = {
        'conditions': {
            'match': {
                'type': 'StasisStart',
                'application': 'testsuite'
            },
        },
        'count': 1,
        'callback': {
            'module': 'audio_analyzer',
            'method': 'on_start'
        }}

    on_stasis_end = {
        'conditions': {
            'match': {
                'type': 'StasisEnd',
                'application': 'testsuite'
            },
        },
        'count': 1,
        'callback': {
            'module': 'audio_analyzer',
            'method': 'on_stasis_end'
        }}

    def __init__(self, test_path='', test_config=None):
        """Constructor for a test object

        :param test_path The full path to the test location
        :param test_config The YAML test configuration
        """

        if test_config is None:
            test_config = {}

        # Global conf file path
        test_config['config-path'] = 'tests/codecs/configs/'

        self.output_file = test_config.get('output-file', 'audio_output.wav')

        if not test_config.get('test-iterations'):
            test_config['test-iterations'] = [{
                'channel': 'PJSIP/audio',
                'application': 'Record',
                'data': self.output_file + ',,,k',
                'nowait': 'True'
            }]

        super(Analyzer, self).__init__(test_path, test_config)

        # Get the path to Asterisk and build a path to sounds
        ast = self.ast[0]
        self.sounds_path = (ast.base + ast.directories["astvarlibdir"] +
                            "/sounds/")

        if not test_config.get('events'):
            test_config['events'] = [self.on_stasis_start,
                                     self.on_stasis_end]

        self.playback_file = test_config.get('playback-file')

        # Default tones - 2 seconds of silence, 4 seconds of audio,
        # followed by 2 seconds of silence
        self.tones = test_config.get('tones', [
            {'frequency': 0, 'duration': 2000},
            {'frequency': 440, 'duration': 4000},
            {'frequency': 0, 'duration': 2000}
        ])

        self._events = ari.WebSocketEventModule(test_config, self)
