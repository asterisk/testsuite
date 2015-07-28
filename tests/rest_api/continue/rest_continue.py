'''
Copyright (C) 2013-2014, Digium, Inc.
David M. Lee, II <dlee@digium.com>
Mark Michelson <mmichelson@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
'''

import logging

LOGGER = logging.getLogger(__name__)

# Successive places to continue the call in the dialplan
CONTINUATIONS = [
    None,

    # Specifying no context or extension
    {},
    {'priority': 5},
    {'label': 'eggs'},
    {'priority': 5, 'label': 'toast'},
    {'label': '11'},
    {'priority': 5, 'label': '13'},

    # Specifying extension but no context
    {'extension': 'bacon'},
    {'extension': 'bacon', 'priority': 3},
    {'extension': 'bacon', 'label': 'muffin'},
    {'extension': 'bacon', 'priority': 5, 'label': 'bagel'},
    {'extension': 'bacon', 'label': '9'},
    {'extension': 'bacon', 'priority': 5, 'label': '11'},

    # Specifying context but no extension
    {'context': 'taters'},
    {'context': 'taters', 'priority': 3},
    {'context': 'taters', 'label': 'hollandaise'},
    {'context': 'taters', 'priority': 5, 'label': 'cereal'},
    {'context': 'taters', 'label': '9'},
    {'context': 'taters', 'priority': 5, 'label': '11'},

    # Specifying context and extension
    {'context': 'taters', 'extension': 'biscuit'},
    {'context': 'taters', 'extension': 'biscuit', 'priority': 3},
    {'context': 'taters', 'extension': 'biscuit', 'label': 'sausage'},
    {'context': 'taters', 'extension': 'biscuit', 'priority': 5, 'label': 'pancakes'},
    {'context': 'taters', 'extension': 'biscuit', 'label': '9'},
    {'context': 'taters', 'extension': 'biscuit', 'priority': 5, 'label': '11'},
]

# Spacing used in this list helps line up with continuations in previous list
EXPECTATIONS = [
    's@default:2',

    's@default:3',
    's@default:5',
    's@default:7',
    's@default:9',
    's@default:11',
    's@default:13',

    'bacon@default:1',
    'bacon@default:3',
    'bacon@default:5',
    'bacon@default:7',
    'bacon@default:9',
    'bacon@default:11',

    's@taters:1',
    's@taters:3',
    's@taters:5',
    's@taters:7',
    's@taters:9',
    's@taters:11',

    'biscuit@taters:1',
    'biscuit@taters:3',
    'biscuit@taters:5',
    'biscuit@taters:7',
    'biscuit@taters:9',
    'biscuit@taters:11',
]

CURRENT_EVENT = 0


def on_start(ari, event, test_object):
    location = event['args'][0]
    global CURRENT_EVENT

    if location != EXPECTATIONS[CURRENT_EVENT]:
        LOGGER.error("Stasis entered from {0}, expected {1}".format(location,
                     EXPECTATIONS[CURRENT_EVENT]))
        return False

    LOGGER.info("Stasis entered from expected location {0}".format(location))
    CURRENT_EVENT += 1
    if CURRENT_EVENT == len(CONTINUATIONS):
        ari.delete('channels', event['channel']['id'])
        return True

    ari.post('channels', event['channel']['id'], 'continue',
             **CONTINUATIONS[CURRENT_EVENT])
    return True


def on_end(ari, event, test_object):
    # We don't really care about StasisEnd until the final one
    if CURRENT_EVENT == len(CONTINUATIONS):
        LOGGER.info("Final StasisEnd received. Stopping reactor")
        test_object.stop_reactor()

    return True
