#!/usr/bin/env python
"""Pluggable module registries

Copyright (C) 2014, Digium, Inc.
Kinsey Moore <kmoore@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
"""
import logging
import re

LOGGER = logging.getLogger(__name__)


class PluggableRegistry(object):
    """Registry for pluggable modules"""

    def __init__(self):
        self.registry = {}

    def register(self, key, factory):
        """Register a module"""
        self.registry[key] = factory

    def check(self, key):
        """Check whether a module factory exists for the given key"""
        if key in self.registry:
            return True
        return False

    def get_class(self, key):
        """Get the class for a module"""
        return self.registry[key]

PLUGGABLE_EVENT_REGISTRY = PluggableRegistry()
PLUGGABLE_ACTION_REGISTRY = PluggableRegistry()


def var_replace(text, values):
    """ perform variable replacement on text

    This allows a parameters to be written to include variables from the
    arbitrarily structured object provided by an ARI or AMI event like so:
    from ARI to ARI: Uri: 'playbacks/{playback.id}/control'
    from AMI to AMI: Channel: '{channel}'
    from AMI to ARI: Uri: 'channels/{uniqueid}/play'
    from ARI to AMI: Channel: '{channel.name}'

    :param text: text with optional {var} entries
    :param values: nested dict of values to get replacement values from
    """
    if not isinstance(text, str):
        return text

    for match in re.findall(r'{[^}]*}', text):
        value = values
        for var in match[1:-1].split('.'):
            if not var in value:
                LOGGER.error('Unable to replace variables in %s from %s',
                             text, values)
                return None
            value = value[var]
        text = text.replace(match, value)

    return text
