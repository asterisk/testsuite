'''
Copyright (C) 2014, Digium, Inc.
Mark Michelson <mmichelson@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
'''

import logging

LOGGER = logging.getLogger(__name__)


class PlayFile(object):
    def __init__(self):
        self.channel_id = None
        self.bridge_id = None
        self.first_playback_started = False
        self.first_playback_finished = False
        self.second_playback_started = False
        self.second_playback_finished = False


TEST = PlayFile()


def ari_debug(func):
    def print_debug(ari, event, test_object):
        LOGGER.debug("%s(%r)" % (func.__name__, event))
        return func(ari, event, test_object)
    return print_debug


@ari_debug
def on_start(ari, event, test_object):
    TEST.channel_id = event['channel']['id']
    TEST.bridge_id = ari.post('bridges').json()['id']
    ari.post('channels', TEST.channel_id, 'answer')
    ari.post('bridges', TEST.bridge_id, 'addChannel', channel=TEST.channel_id)
    return True


@ari_debug
def on_playback_started1(ari, event, test_object):
    assert not TEST.first_playback_started
    assert not TEST.first_playback_finished
    assert not TEST.second_playback_started
    assert not TEST.second_playback_finished
    TEST.first_playback_started = True
    return True


@ari_debug
def on_playback_finished1(ari, event, test_object):
    assert TEST.first_playback_started
    assert not TEST.first_playback_finished
    assert not TEST.second_playback_started
    assert not TEST.second_playback_finished
    TEST.first_playback_finished = True
    return True


@ari_debug
def on_playback_started2(ari, event, test_object):
    assert TEST.first_playback_started
    assert TEST.first_playback_finished
    assert not TEST.second_playback_started
    assert not TEST.second_playback_finished
    TEST.second_playback_started = True
    return True


@ari_debug
def on_playback_finished2(ari, event, test_object):
    assert TEST.first_playback_started
    assert TEST.first_playback_finished
    assert TEST.second_playback_started
    assert not TEST.second_playback_finished
    TEST.second_playback_finished = True
    ari.post('bridges', TEST.bridge_id, 'removeChannel',
             channel=TEST.channel_id)
    return True


@ari_debug
def on_leave(ari, event, test_object):
    assert TEST.first_playback_started
    assert TEST.first_playback_finished
    assert TEST.second_playback_started
    assert TEST.second_playback_finished
    ari.delete('bridges', TEST.bridge_id)
    ari.delete('channels', TEST.channel_id)
    return True
