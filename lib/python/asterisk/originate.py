#!/usr/bin/env python
""" Pluggable module for originating calls

Copyright (C) 2014, Digium, Inc.
Kevin Harwell <kharwell@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
"""

import sys
import logging

from twisted.internet import reactor

import json
import requests

from . import ari

LOGGER = logging.getLogger(__name__)


def cli_originate(ast, tech_data, application=None, app_data=None,
                  exten=None, context=None):
    """Originate a call using the CLI. Note, an application or extension should
    be specified.

    arguments:
    tech_data: channel technology used
    application: the application to dial into (optional)
    app_data: data used by the application (optional)
    exten: the extension to dial (optional)
    context: the context for the extension (optional)
    """
    if application:
        ast.cli_exec("channel originate %s application %s %s" %
                     (tech_data, application, app_data))
    if exten:
        ast.cli_exec("channel originate %s extension %s@%s" %
                     (tech_data, exten, context))

    return None


def ami_originate(ami, **kwargs):
    """Originate a call using AMI."""
    return ami.originate(**kwargs)


def ari_originate(ari, **kwargs):
    """Originate a call using ARI."""
    url = ari.build_url('channels')

    # variables are passed as a body param so need to extract it
    data = ({'variables': kwargs['variables']}
            if 'variables' in kwargs else None)

    params = (dict((i, kwargs[i]) for i in set(
        kwargs.keys()) - set('variables')))

    headers = {'Content-type': 'application/json'}

    resp = requests.post(
        url, params=params, headers=headers, auth=ari.userpass,
        data=json.dumps(data) if data else None)

    return (None if resp.status_code == 200 else
            '(' + str(resp.status_code) + ') ' +
            resp.json().get('message', 'Failed'))


class Originator(object):
    """Originate a call.

    Configuration options include:
        ignore-failures: if 'True' ignore any failures on originate
            defaults to 'False'
        wait-start: number of seconds to wait before starting the origination
            process.  defaults to 1.
        max-originate: Total number of calls to originate.
            defaults to 1.
        interval: interval, in seconds, at which channels are originated.
            defaults to 1.
        originate-params: type specific parameters used during origination.
        asterisk-instance: the asterisk instance channels are originated on.
            defaults to 1.
    """
    def __init__(self, config, test_obj, originate):
        """Initialize and configure the Originator object."""
        self.test_obj = test_obj
        self.test_obj.set_passed(True)

        if config.get('ignore-failures', False):
            # override default behavior to do nothing with the failure
            self._failure = lambda result: True

        self.wait_start = config.get('wait_start', 1)
        self.max_originate = config.get('max-originate', 1)
        self.interval = config.get('interval', 1)
        self.params = config.get('originate-params', None)
        self.asterisk_instance = config.get('asterisk-instance', 1) - 1

        self.num_originated = 0
        self.originate = originate

        self.test_obj.register_ami_observer(self._register_ami_event)

    def _failure(self, result):
        """Handle failure to originate error"""
        LOGGER.error("Error originating: %s" % result)
        self.test_obj.set_passed(False)
        self.test_obj.stop_reactor()

    def _originate_deferred(self, obj):
        """Originate calls that return a deferred object."""
        self.originate(obj, **self.params).addErrback(self._failure)
        self._originate_again(obj, self._originate_deferred)

    def _originate(self, obj):
        """Originate calls that return a possible string result.  Expects
        a string result only on error.
        """
        res = self.originate(obj, **self.params)
        if res:
            self._failure(res)
        self._originate_again(obj, self._originate)

    def _originate_again(self, obj, fun):
        """Originate the next call if needed.  Once all calls have been
        originated raise an 'OriginateComplete' event.
        """
        LOGGER.debug('Call originated')
        self.num_originated += 1
        if self.num_originated < self.max_originate:
            reactor.callLater(self.interval, fun, obj)
        else:
            LOGGER.debug('Finished originating call(s)')
            reactor.callLater(
                self.interval, lambda: self.ami.userEvent('OriginateComplete'))

    def _register_ami_event(self, ami):
        """Register to listen for ami events. Child classes should override
        if listening for specific AMI events.
        """
        if ami.id != self.asterisk_instance:
            return False

        self.ami = ami
        LOGGER.debug('Registering AMI event(s)')
        return True


class CliOriginator(Originator):
    """Originate calls using the CLI."""
    def __init__(self, config, test_obj):
        """Initialize an CliOriginator object and start originating
        calls once all asterisk instances are up.
        """
        super(CliOriginator, self).__init__(
            config, test_obj, cli_originate)
        test_obj.register_start_observer(
            (lambda ast: reactor.callLater(
                self.wait_start, self._originate,
                ast[self.asterisk_instance])))


class AmiOriginator(Originator):
    """Originate calls using AMI."""
    def __init__(self, config, test_obj):
        """Initialize an AmiOriginator object."""
        super(AmiOriginator, self).__init__(
            config, test_obj, ami_originate)

    def _register_ami_event(self, ami):
        """Start originating once AMI is up."""
        if super(AmiOriginator, self).register_ami_event(ami):
            reactor.callLater(
                self.wait_start, self._originate_deferred, ami)


class AriOriginator(Originator):
    """Originate calls using ARI and start originating
        calls once all asterisk instances are up.
    """
    def __init__(self, config, test_obj):
        """Initialize an AriOriginator object"""
        super(AriOriginator, self).__init__(
            config, test_obj, ari_originate)
        test_obj.register_start_observer(
            (lambda ast: reactor.callLater(
                self.wait_start, self._originate, test_obj.ari)))
