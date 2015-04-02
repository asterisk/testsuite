#!/usr/bin/env python
"""
Copyright (C) 2015, Digium, Inc.
Ashley Sanders <asanders@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
"""

import sys
import logging
import time
import uuid

sys.path.append("lib/python")
sys.path.append("tests/rest_api/applications")

from asterisk.ari import ARI, AriClientFactory
from stasisstatus.observable_object import ObservableObject
from twisted.internet import defer, reactor

LOGGER = logging.getLogger(__name__)


class AriClient(ObservableObject):
    """The ARI client.

     This class serves as a facade for ARI and AriClientFactory. It is
     responsible for creating and persisting the connection state needed to
     execute a test scenario.
     """

    def __init__(self, host, port, credentials, name='testsuite'):
        """Constructor.

        Keyword Arguments:
        host                  -- The [bindaddr] of the Asterisk HTTP web
                                 server.
        port                  -- The [bindport] of the Asterisk HTTP web
                                 server.
        credentials           -- User credentials for ARI. A tuple.
                                 E.g.: ('username', 'password').
        name                  -- The name of the app to register in Stasis via
                                 ARI (optional) (default 'testsuite').
        """


        super(AriClient, self).__init__(name, ['on_channelcreated',
                                               'on_channeldestroyed',
                                               'on_channelstatechange',
                                               'on_channelvarset',
                                               'on_client_start',
                                               'on_client_stop',
                                               'on_stasisend',
                                               'on_stasisstart',
                                               'on_ws_open',
                                               'on_ws_closed'])
        self.__ari = None
        self.__factory = None
        self.__ws_client = None
        self.__channels = []
        self.__host = host
        self.__port = port
        self.__credentials = credentials

    def connect_websocket(self):
        """Creates an AriClientFactory instance and connects to it."""

        LOGGER.debug('{0} About to reset my state!'.format(self))
        self.__reset()
        while not self.clean:
            LOGGER.debug('{0} I\'m not so fresh so clean.'.format(self))
            time.sleep(1)

        LOGGER.debug('{0} Connecting web socket.'.format(self))

        self.__ari = ARI(self.__host, userpass=self.__credentials)
        self.__factory = AriClientFactory(receiver=self,
                                          host=self.__host,
                                          port=self.__port,
                                          apps=self.name,
                                          userpass=self.__credentials)
        self.__factory.connect()
        return

    def __delete_all_channels(self):
        """Deletes all the channels."""

        if len(self.__channels) == 0:
            return

        channels = list().extend(self.__channels)
        if self.__ari is not None:
            allow_errors = self.__ari.allow_errors
            self.__ari.set_allow_errors(True)
            for channel in channels:
                self.hangup_channel(channel)
            self.__ari.set_allow_errors(allow_errors)
        return

    def disconnect_websocket(self):
        """Disconnects the web socket."""

        msg = '{0} '.format(self)

        if self.__ws_client is None:
            info = 'Cannot disconnect; no web socket is connected.'
            LOGGER.debug(msg + info)
            return self

        if self.__ari is not None:
            warning = 'Disconnecting web socket with an active ARI connection.'
            LOGGER.warn(msg + warning)

        LOGGER.debug(msg + 'Disconnecting the web socket.')
        self.__ws_client.transport.loseConnection()
        return self

    def hangup_channel(self, channel_id):
        """Deletes a channel.

        Keyword Arguments:
        channel_id            -- The id of the channel to delete.

        Returns:
        The JSON response object from the DELETE to ARI.

        Raises:
        ValueError
        """

        msg = '{0} '.format(self)

        if self.__ari is None:
            msg += 'Cannot hangup channel; ARI instance has no value.'
            raise ValueError(msg.format(self))

        LOGGER.debug(msg + 'Deleting channel [{0}].'.format(channel_id))

        try:
            self.__channels.remove(channel_id)
        except ValueError:
            pass

        return self.__ari.delete('channels', channel_id)

    def on_channelcreated(self, message):
        """Callback for the ARI 'ChannelCreated' event.

        Keyword Arguments:
        message               -- the JSON message
        """

        channel = message['channel']['id']
        if channel not in self.__channels:
            self.__channels.append(channel)

        self.notify_observers('on_channelcreated', message)

    def on_channeldestroyed(self, message):
        """Callback for the ARI 'ChannelDestroyed' event.

        Keyword Arguments:
        message               -- the JSON message
        """

        channel = message['channel']['id']
        try:
            self.__channels.remove(channel)
        except ValueError:
            pass

        self.notify_observers('on_channeldestroyed', message)

    def on_channelstatechange(self, message):
        """Callback for the ARI 'ChannelStateChange' event."""

        self.notify_observers('on_channelstatechange', message)

    def on_channelvarset(self, message):
        """Callback for the ARI 'ChannelVarset' event.

        Keyword Arguments:
        message               -- the JSON message
        """

        self.notify_observers('on_channelvarset', message)

    def on_client_start(self):
        """Notifies the observers of the 'on_client_start' event."""

        LOGGER.debug('{0} Client is started.'.format(self))
        self.notify_observers('on_client_start', None, True)

    def on_client_stop(self):
        """Notifies the observers of the 'on_client_stop' event."""

        LOGGER.debug('{0} Client is stopped.'.format(self))
        self.notify_observers('on_client_stop', None, True)

    def on_stasisend(self, message):
        """Callback for the ARI 'StasisEnd' event

        Keyword Arguments:
        message               -- the JSON message
        """

        self.notify_observers('on_stasisend', message)

    def on_stasisstart(self, message):
        """Callback for the ARI 'StasisEnd' event

        Keyword Arguments:
        message               -- the JSON message
        """

        self.notify_observers('on_stasisstart', message)

    def on_ws_closed(self, ws_client):
        """Callback for AriClientProtocol 'onClose' handler.

        Keyword Arguments:
        ws_client             -- The AriClientProtocol object that raised
                                 the event.
        """

        LOGGER.debug('{0} WebSocket connection closed.'.format(self))
        self.__ws_client = None
        self.notify_observers('on_ws_closed', None)

    def on_ws_event(self, message):
        """Callback for AriClientProtocol 'onMessage' handler.

        Keyword Arguments:
        message               -- The event payload.
        """

        LOGGER.debug("{0} In on_ws_event; message={1}".format(self, message))

        event = 'on_{0}'.format(message.get('type').lower())

        if event == 'on_ws_open' or event == 'on_ws_closed':
            return

        callback = getattr(self, event, None)
        if callback and callable(callback):
            callback(message)
            self.notify_observers(event, message)

    def on_ws_open(self, ws_client):
        """Callback for AriClientProtocol 'onOpen' handler.

        Keyword Arguments:
        ws_client             -- The AriClientProtocol object that raised
                                 the event.
        """

        LOGGER.debug('{0} WebSocket connection opened.'.format(self))
        self.__ws_client = ws_client
        self.notify_observers('on_ws_open', None)
        self.on_client_start()

    def originate(self, app_name=None, resource=None):
        """Originates a channel.

        Keyword Arguments:
        app_name              --  The name of the Stasis app. (optional)
                                  (default None). If not provided, the app name
                                  that was registered with Stasis will be used.
        resource              --  The resource to use to construct the endpoint
                                  for the ARI request. (optional)
                                  (default None.) If no value is provided,
                                  resource will automatically be generated in
                                  the form: 'LOCAL/<app_name>@Acme'.

        Returns:
        The JSON response object from the POST to ARI.

        Raises:
        ValueError
        """

        msg = '{0} '.format(self)

        if self.__ari is None:
            msg += 'Cannot originate channel; ARI instance has no value.'
            raise ValueError(msg)

        app_name = app_name or self.name
        endpoint = 'LOCAL/{0}@Acme'.format(resource or app_name)
        channel = {'app': app_name,
                   'channelId': str(uuid.uuid4()),
                   'endpoint': endpoint}

        msg += 'Originating channel [{0}].'
        LOGGER.debug(msg.format(channel['channelId']))
        return self.__ari.post('channels', **channel)

    def __reset(self):
        """Resets the AriClient to its initial state.

        Returns:
        A twisted.defer instance.
        """

        if self.clean:
            return defer.Deferred()
        else:
            return self.__tear_down()

    def start(self):
        """Starts the client."""

        LOGGER.debug('{0} Starting client connections.'.format(self))
        self.connect_websocket()

    def stop(self):
        """Stops the client."""

        LOGGER.debug('{0} Stopping client connections.'.format(self))
        self.suspend()
        self.__reset()

    def __tear_down(self):
        """Tears down the channels and web socket.

        Returns:
        A twisted.defer instance.
        """

        def wait_for_it(deferred=None, run=0):
            """Disposes each piece, one at a time.


            The first run (run=0) initialized the deferred and kicks of
            the process to destroy all of our channels.

            The second run (run=1) waits for all the channels to be
            destroyed then kicks off the process to disconnect the web socket.

            The third run (run=2) waits for the web socket to
            disconnect then cleans up the remaining state variables.

            Keyword Arguments:
            deferred              -- The twisted.defer instance to use for
                                     chaining callbacks (optional)
                                     (default None).
            run                   -- The current phase of tear down:
                                     0=Entry phase
                                     1=Waiting for ARI to destroy all channels
                                     2=Calls ARI to Disconnects the web socket
                                     3=Waiting for ARI to disconnect the web
                                       socket

            Returns:
            The a twisted.defer instance.
            """

            msg = '{0} '.format(self)

            if not deferred:
                deferred = defer.Deferred()
                self.suspend()
            if run is 0:
                LOGGER.debug(msg + 'Tearing down active connections.')
                self.__delete_all_channels()
                reactor.callLater(2, wait_for_it, deferred, 1)
            elif run is 1:
                if len(self.__channels) > 0:
                    msg += 'Waiting for channels to be destroyed.'
                    LOGGER.debug(msg)
                    reactor.callLater(2, wait_for_it, deferred, 1)
                reactor.callLater(2, wait_for_it, deferred, 2)
            elif run is 2:
                LOGGER.debug(msg + 'Disconnecting web socket.')
                self.__ari = None
                self.__factory = None
                self.disconnect_websocket()
                reactor.callLater(2, wait_for_it, deferred, 3)
            elif run is 3:
                if self.__ws_client is not None:
                    msg += 'Waiting for web socket to be destroyed.'
                    LOGGER.debug(msg)
                    reactor.callLater(2, wait_for_it, deferred, 3)
                else:
                    LOGGER.debug(msg + 'Client successfully torn down.')
                    reactor.callLater(0, self.on_client_stop)
                    reactor.callLater(2, self.reset_registrar)
                    deferred.callback(self.resume())
        return wait_for_it()

    @property
    def clean(self):
        """Returns True if the client has no orphaned connections
        needing to be torn down. False otherwise."""

        if len(self.__channels) == 0:
            LOGGER.debug('{0} No channels!'.format(self))
            if self.__ws_client is None:
                LOGGER.debug('{0} No ws_client!'.format(self))
                if self.__ari is None:
                    LOGGER.debug('{0} No ari!'.format(self))
                    if self.__factory is None:
                        LOGGER.debug('{0} No factory!'.format(self))
                        LOGGER.debug('{0} I\'m clean!'.format(self))
                        return True
        return False
