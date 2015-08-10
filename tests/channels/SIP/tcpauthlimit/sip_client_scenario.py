'''
Copyright (C) 2015, Digium, Inc.
Ashley Sanders <asanders@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
'''

import sys
import logging

sys.path.append("lib/python/asterisk")
sys.path.append("tests/channels/SIP")

from twisted.internet import defer, reactor
from twisted.internet.protocol import ClientFactory, Protocol

LOGGER = logging.getLogger(__name__)


class SipClient(Protocol):
    """Client connection protocol."""

    def __init__(self, addr, on_connect, client_id=None):
        """Constructor.

        Keyword Arguments:
        addr                   -- The client address as a
                                  twisted.internet.interfaces.IAddress.
        on_connect             -- Callback to invoke when the client connection
                                  is established.
        """

        self.__addr = addr
        self.__on_connect = on_connect
        self.__id = client_id

    def connectionMade(self):
        """Called when a connection is made.

        Overrides twisted.internet.protocol.Protocol.connectionMade
        """

        msg = '{0} connection was successfully established.'.format(self)
        LOGGER.debug(msg)

        self.__on_connect()
        Protocol.connectionMade(self)

        msg = '%d: An apple a day keeps the doctor away\r\n'
        for i in range(0, 1000):
            self.transport.write(msg % i)

    def disconnect(self):
        """Disconnects the client connection."""

        msg = '{0} disconnecting.'.format(self)
        LOGGER.debug(msg)
        self.transport.loseConnection()

    def __format__(self, format_spec):
        """Overrides default format handling for 'self'."""

        return self.__class__.__name__  + ' [' + self.__id + ']:'

class SipClientFactory(ClientFactory):
    """Factory for building SIP webSocket clients."""

    def __init__(self, on_connecting_changed, on_connection_lost, client_id):
        """Constructor.

        Keyword arguments:
        on_connecting_changed  -- Callback to invoke when the client protocol
                                  connection state changes.
        on_connection_lost     -- Callback to invoke when the client protocol
                                  destroys its transport connection.
        client_id              -- The id to give to built clients.
        """

        self.__on_connecting_changed = on_connecting_changed
        self.__on_connection_lost = on_connection_lost
        self.__id = client_id

        self.__protocol = None
        self.__connected = None

    def buildProtocol(self, addr):
        """Twisted overload used to create the client connection.

        Overrides twisted.internet.protocol.ClientFactory.buildProtocol

        Keyword Arguments:
        addr                   -- The client address as a
                                  twisted.internet.interfaces.IAddress.
        """

        msg = '{0} Building a SipClient protocol.'.format(self)
        LOGGER.debug(msg)

        if self.__protocol is not None:
            self.disconnect()

        self.__protocol = SipClient(addr, self.__on_client_connection_made)
        return self.__protocol

    def clientConnectionFailed(self, connector, reason):
        """Called when a client has failed to connect.

        Overrides twisted.internet.protocol.ClientFactory.clientConnectionFailed

        Keyword Arguments:
        connector              -- The TCP connector.
        reason                 -- The failure reason.
        """

        msg = '{0} Failed to establish a connection.'.format(self)
        self.__on_client_state_change(False,
                                      msg,
                                      self.__on_connecting_changed,
                                      reason)
        ClientFactory.clientConnectionFailed(self, connector, reason)

    def clientConnectionLost(self, connector, reason):
        """Called when an established connection is lost.

        Overrides twisted.internet.protocol.ClientFactory.clientConnectionLost

        Keyword Arguments:
        connector              -- The TCP connector.
        reason                 -- The failure reason.
        """

        msg = '{0} Connection has been lost.'.format(self)
        self.__on_client_state_change(False,
                                      msg,
                                      self.__on_connection_lost,
                                      reason)
        ClientFactory.clientConnectionLost(self, connector, reason)

    def disconnect(self):
        """Disconnects the client protocol."""

        msg = '{0} Destroying transport connection.'.format(self)
        LOGGER.debug(msg)
        self.__protocol.disconnect()

    def __format__(self, format_spec):
        """Overrides default format handling for 'self'."""

        return self.__class__.__name__ + ' [' + self.client_id + ']:'

    def __on_client_connection_made(self):
        """Handles the connectionMade event from the client protocol."""

        msg = '{0} Connection has been established.'.format(self)
        self.__on_client_state_change(True,
                                      msg,
                                      self.__on_connecting_changed,
                                      self)

    def __on_client_state_change(self, connected, message, callback, payload):
        """Handles connection state changes.

        Keyword Arguments:
        connected              -- Whether or not the state change resulted in
                                  the client protocol being connected.
        message                -- The message to write to the log.
        callback               -- The callback to invoke for notifing the
                                  observer of the state change.
        payload                -- The callback payload.
        """

        self.__connected = connected
        LOGGER.debug(message)
        callback(payload)

    @property
    def connecting(self):
        """Whether or not the the client is trying to establish a connection.

        Returns:
        True if the client has finished connecting, False otherwise.
        """

        return self.__connected is None

    @property
    def connected(self):
        """Whether or not the client protocol is connected.

        Returns:
        True if the client is connected. Otherwise, returns False.
        """

        return False if self.connecting else self.__connected

    @property
    def client_id(self):
        """Returns the id for the client protocol."""

        return self.__id


class SipClientScenario(object):
    """The test scenario for testing SIP socket creation.

    This scenario confirms that Asterisk honors its tcpauthlimit property by
    trying to create more SIP sockets than the configuration specifies as the
    limit.
    """

    def __init__(self, scenario_id, skip=None, host='127.0.0.1', port=5060,
                 allowed_connections=0):
        """Constructor.

        Keyword Arguments:
        scenario_id            -- The id for this scenario. Used for logging.
        skip                   -- A message to display if the scenario is to
                                  be suspended from executing.
                                  Optional. Default: None.
        host                   -- The remote host address to use for a client
                                  connection. Optional. Default: 127.0.0.1.
        port                   -- The remote host port to use for a client
                                  connection. Optional. Default: 5060.
        allowed_connections    -- The number of clients allowed by chan_sip.
                                  Optional. Default: 0.
        """

        self.__scenario_id = scenario_id
        self.__status = skip

        self.__host = host
        self.__port = port
        self.__allowed_connections = allowed_connections

        self.__passed = None
        self.__started = None
        self.__stopping = None

        self.__clients = None
        self.__iterator = None

        self.__on_started = None
        self.__on_complete = None

        self.__init_results()

    def __disconnect_client(self, client):
        """Disconnects the given client.

        Keyword Arguments:
        client             -- The client to disconnect.
        """

        if client is None and self.__stopping:
            self.__stopping = False
            return

        msg = '{0} Disconnecting client[{1}]...'.format(self, client.client_id)
        LOGGER.debug(msg)
        client.disconnect()

    def __evaluate_results(self, message):
        """Evaluates the test scenario results.

        Keyword Arguments:
        message                -- The event payload.
        """

        msg = '{0} Evaluating scenario results...'.format(self)
        LOGGER.debug(msg)

        connected_clients = sum(client.connected for client in self.__clients)
        self.passed = connected_clients == self.__allowed_connections

        if not self.passed:
            msg = '{0} Scenario failed.\n'
            msg += '\tBased on the test configuration, I expected to receive:\n'
            msg += '\t\t{1} client connections.\n'
            msg += '\tHere is what I actually received:\n'
            msg += '\t\t{2} client connections.'
            LOGGER.error(msg.format(self,
                                    self.__allowed_connections,
                                    connected_clients))
        else:
            LOGGER.info('{0} Congrats! The scenario passed.'.format(self))

        self.__on_complete.callback(self)
        return message

    def __format__(self, format_spec):
        """Overrides default format handling for 'self'."""

        return self.__class__.__name__ + ':'

    def __get_next_client(self):
        """Tries to get the next client from the list.

        Returns:
        A client if the iteration is not complete. Else returns None.
        """

        client = None
        try:
            client = self.__iterator.next()
        except StopIteration:
            if self.__stopping:
                self.__clients = []
        return client

    def __init_results(self):
        """Initialize the scenario results."""

        self.__passed = None
        self.__started = False
        self.__stopping = False

        self.__clients = self.__initialize_clients()
        self.__iterator = iter(self.__clients)

        self.__on_started = defer.Deferred()
        self.__on_complete = defer.Deferred()

    def __initialize_clients(self):
        """Builds the SIP Client for this scenario.

        Returns:
        A list of n SipClientFactory instances, where n equals
        self.__allowed_connections + 1.
        """

        clients = list()

        for i in range(0, self.__allowed_connections + 1):
            factory = SipClientFactory(self.__on_client_state_change,
                                       self.__on_client_disconnect,
                                       i)
            clients.append(factory)

        return clients

    def __on_client_disconnect(self, sender):
        """Handles a client disconnect event.

        Keyword Arguments:
        sender             -- The client that was disconnected.
        """

        client = sender.client_id
        LOGGER.debug('{0} Client[{1}] is disconnected.'.format(self,
                                                               client))

        if self.__stopping:
            self.__disconnect_client(self.__get_next_client())

    def __on_client_state_change(self, sender):
        """Handler for client connection state changes.

        Keyword Arguments:
        sender                 -- The client who sent the notification.
        """

        if self.__started:
            return

        msg = '{0} Received a state change notification from client [{1}].'
        LOGGER.debug(msg.format(self, sender.client_id))

        if len(self.__clients) < sender.client_id:
            msg ='{0} Ruh-roh.'
            msg += ' I received a message for a client that I didn\'t create.'
            LOGGER.warning(msg.format(self))
            return

        if all(client.connecting is False for client in self.__clients):
            LOGGER.debug('{0} All clients have started.'.format(self))
            self.__started = True
            self.__on_started.callback(self)

    def __on_scenario_teardown(self, message):
        """Disconnects the clients.

        Keyword Arguments:
        message                -- The event payload.
        """

        LOGGER.debug('{0} Tearing down the scenario.'.format(self))
        self.__stopping = True

        deferred = defer.Deferred()
        deferred.addCallback(self.__disconnect_client)
        deferred.callback(self.__get_next_client())

        return message

    def run(self):
        """Runs the SIP client scenario.

        Returns:
        A twisted.internet.defer.Deferred instance that can be used to
        determine when the scenario is complete.
        """

        if self.suspended:
            LOGGER.debug('{0} Scenario suspended; nothing to do.'.format(self))
            self.passed = False
            return None

        LOGGER.debug('{0} Starting scenario...'.format(self))

        self.__init_results()
        self.__on_started.addCallback(self.__evaluate_results)
        self.__on_started.addCallback(self.__on_scenario_teardown)

        self.__start_clients()
        return self.__on_complete

    def __start_clients(self):
        """Starts connection process for this scenario's clients."""

        msg = '{0} Attempting to connect {1} clients to Asterisk...'
        LOGGER.debug(msg.format(self, len(self.__clients)))

        for client in self.__clients:
            reactor.connectTCP(self.__host, self.__port, client)

    @property
    def finished(self):
        """Whether or not the this scenario has finished execution.

        Returns:
        True if the scenario has finished execution. False otherwise.
        """

        return self.__passed is not None

    @property
    def passed(self):
        """The results of the scenario.

        Returns:
        False if the scenario has not finished execution. Else, True if the
        scenario was successful. False otherwise.
        """

        if self.suspended:
            return False

        return False if not self.finished else self.__passed

    @passed.setter
    def passed(self, value):
        """Safely set the pass/fail value for this scenario."""

        if self.__passed is False:
            return

        self.__passed = value

    @property
    def scenario_id(self):
        """Returns the id for this scenario."""

        return self.__scenario_id

    @property
    def status(self):
        """Returns a message indicating the suspended status of the scenario."""

        return self.__status

    @property
    def suspended(self):
        """Whether or not the scenario has been suspended from execution.

        Returns:
        True if the scenario is suspended, False otherwise.
        """

        return self.status is not None
