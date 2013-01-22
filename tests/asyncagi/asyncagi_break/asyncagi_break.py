'''
Copyright (C) 2012, Digium, Inc.
Matt Jordan <mjordan@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
'''

import logging

LOGGER = logging.getLogger(__name__)

def async_start(ami, event):
    ''' Callback called when an AsyncAMI event is received indicating that the
    AsyncAGI session has started.
    '''

    LOGGER.info('Requesting playback of monkeys')
    msg = {'Action': 'AGI',
           'Channel': event['channel'],
           'Command': 'STREAM FILE tt-monkeys ""',}
    ami.sendMessage(msg)

def async_break(ami, event):
    ''' Callback called when we notice that we've started the tt-monkeys
    playback.

    Note that we expect this to be a synchronous breaking of the AsyncAGI
    application '''

    LOGGER.info('Requesting an async break')
    msg = {'Action': 'AGI',
           'Channel': event['channel'],
           'Command': 'ASYNCAGI BREAK'}
    ami.sendMessage(msg)
