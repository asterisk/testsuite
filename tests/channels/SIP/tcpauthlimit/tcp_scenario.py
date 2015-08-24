#!/usr/bin/env python
'''
Copyright (C) 2015, Digium, Inc.
Ashley Sanders <asanders@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
'''

import socket
import logging

from twisted.internet import defer, error, reactor
from twisted.internet.protocol import ClientFactory
from twisted.internet.tcp import EWOULDBLOCK
from twisted.protocols.basic import LineReceiver
from twisted.python import failure

LOGGER = logging.getLogger(__name__)

class ConnectionState(object):
    """An enumeration to describe the connection state of a client."""

    CONNECTING = 0
    CONNECTED = 1
    DONE = 2
    LOST = 3
    FAILED = 4

    @staticmethod
    def get_state_name(state):
        """Gets the name of the given connection state.

        Keyword Arguments:
        state                  -- The connection state.
        """

        if state == ConnectionState.CONNECTING:
            return 'CONNECTING'
        elif state == ConnectionState.CONNECTED:
            return 'CONNECTED'
        elif state == ConnectionState.DONE:
            return 'DONE'
        elif state == ConnectionState.LOST:
            return 'LOST'
        elif state == ConnectionState.FAILED:
            return 'FAILED'
        return 'UNKNOWN'

class TcpClient(LineReceiver):
    """Client connection protocol."""

    def __init__(self, client_id, hostaddr, clientaddr, on_connection_change):
        """Constructor.

        Keyword Arguments:
        client_id              -- The id to use for this client.
        hostaddr               -- The host address as a
                                  twisted.internet.interfaces.IAddress.
        clientaddr             -- A (host, port) tuple of the local address to
                                  bind to the client.
        on_connection_change   -- Callback to invoke when the client connection
                                  is established.
        """

        self.__client = '%s:%d' % (clientaddr[0], clientaddr[1])
        self.__connection_state = ConnectionState.CONNECTING
        self.__host = '%s:%d' % (hostaddr.host, hostaddr.port)
        self.__id = client_id
        self.__lines = []
        self.__on_connection_change = on_connection_change

    def connectionLost(self, reason=failure.Failure(error.ConnectionDone())):
        """Called when the connection is shut down.

        Keyword Arguments:
        reason                 -- The reason for the connection loss as a
                                  twisted.python.failure.Failure instance.
                                  Optional. Default: result of
                                  failure.Failure(error.ConnectionDone()).
        """

        if (self.__connection_state == ConnectionState.CONNECTING or
            self.__connection_state == ConnectionState.CONNECTED):
            self.__connection_state = ConnectionState.LOST

    def connectionMade(self):
        """Called when a connection is made.

        Overrides twisted.internet.protocols.basic.LineReceiver.connectionMade
        """

        msg = '{0} Initial connection to {1} established.'
        LOGGER.debug(msg.format(self, self.host))

        connection_state = self.__sync_socket()
        if connection_state != ConnectionState.CONNECTED:
            msg = '{0} Connection state to {1} : {2}'
            state = ConnectionState.get_state_name(connection_state)
            LOGGER.debug(msg.format(self, self.host, state))
            self.disconnect()
        else:
            msg = '{0} Connection to {1} successful.'
            LOGGER.debug(msg.format(self, self.host))

        self.__connection_state = connection_state
        self.__on_connection_change()

    def disconnect(self):
        """Disconnects the client connection."""

        if self.connection_state == ConnectionState.CONNECTED:
            return

        msg = '{0} Disconnecting the transport...'.format(self)
        LOGGER.debug(msg)
        self.transport.loseConnection()

    def fail_connection(self):
        """Fails the connection.

        In the event that the connector fails and we don't get the notification,
        this method should be invoked from the factory to keep us updated.
        """

        self.__connection_state = ConnectionState.FAILED

    def __format__(self, format_spec):
        """Overrides default format handling for 'self'."""

        return '%s [%s]:' % (self.__class__.__name__, self.__client)

    def lineReceived(self, line):
        """Handler for receiving lines of data from the host.

        Overrides twisted.internet.protocols.basic.LineReceiver.lineReceived

        Keyword Arguments:
        line                   -- The line of data received from the host.
        """

        pass

    def rawDataReceived(self, data):
        """Handler for receiving raw data from the host.

        Overrides twisted.internet.protocols.basic.LineReceiver.rawDataReceived

        Keyword Arguments:
        data                   -- The blob of raw data received from the host.
        """

        pass

    def __sync_socket(self):
        """Attempts to syncronize the socket.

        Sends a battery of Noop messages and then attempts to read from the
        socket. The hope is that either we will catch up that the host has
        rejected the connection or confirm that we are indeed connected to the
        host.
        """

        msg = '{0} Syncronizing the connection state...'.format(self)
        LOGGER.debug(msg)

        msg = '%d: An apple a day keeps the doctor away\r\n'
        for i in range(0, 150):
            self.transport.write(msg % i)
            if i % 10 == 0:
                if self.__try_read() == ConnectionState.CONNECTED:
                    return ConnectionState.CONNECTED
        return self.__try_read()

    def __try_read(self):
        """Tries to read data from the socket."""

        try:
            self.transport.socket.recv(self.transport.bufferSize)
        except socket.error, se:
            return (
                ConnectionState.DONE if se.args[0] == EWOULDBLOCK
                else ConnectionState.LOST)
        return ConnectionState.CONNECTED

    @property
    def connection_state(self):
        """Returns the connection state for the client.

        Returns:
        ConnectionState.CONNECTING  -- If the client is connecting.
        ConnectionState.CONNECTED   -- If the client is connection to the host
                                       was successful.
        ConnectionState.DONE        -- If the client connection to the host
                                       was rejected by the host.
        ConnectionState.LOST        -- If the client connection to the host was
                                       terminated (by either side).
        """

        return self.__connection_state

    @property
    def host(self):
        """Returns the host used for the client connection."""

        return self.__host


class TcpClientFactory(ClientFactory):
    """Factory for building SIP webSocket clients."""

    def __init__(self, client_id, clientaddr, on_connection_lost):
        """Constructor.

        Keyword arguments:
        client_id              -- The id to give to built clients.
        clientaddr             -- A (host, port) tuple of the local address to
                                  bind to the client.
        on_connection_lost     -- Callback to invoke when the client protocol
                                  destroys its transport connection.
        """

        self.__clientaddr = clientaddr
        self.__done = None
        self.__failed = False
        self.__id = client_id
        self.__on_connection_lost = on_connection_lost
        self.__protocol = None

    def buildProtocol(self, addr):
        """Twisted overload used to create the client connection.

        Overrides twisted.internet.protocol.ClientFactory.buildProtocol

        Keyword Arguments:
        addr                   -- The host address as a
                                  twisted.internet.interfaces.IAddress.
        """

        msg = '{0} Building a TcpClient protocol...'.format(self)
        LOGGER.debug(msg)

        self.disconnect()
        self.__protocol = TcpClient(self.client_id,
                                    addr,
                                    self.__clientaddr,
                                    self.__on_client_connection_made)
        return self.__protocol

    def clientConnectionFailed(self, connector, reason):
        """Called when a client has failed to connect.

        Overrides twisted.internet.protocol.ClientFactory.clientConnectionFailed

        Keyword Arguments:
        connector              -- The TCP connector.
        reason                 -- The reason for the connection failure as a
                                  twisted.python.failure.Failure instance.
        """

        msg = '{0} Failed to establish a connection. Reason: {1}'
        LOGGER.debug(msg.format(self, reason.getErrorMessage()))
        if self.__protocol:
            self.__protocol.fail_connection()
        self.__handle_client_state_change(reason)

    def clientConnectionLost(self, connector, reason):
        """Called when an established connection is lost.

        Overrides twisted.internet.protocol.ClientFactory.clientConnectionLost

        Keyword Arguments:
        connector              -- The TCP connector.
        reason                 -- The reason for the connection loss as a
                                  twisted.python.failure.Failure instance.
        """

        if self.connecting:
            return

        msg = '{0} Connection has been lost. Reason: {1}'
        LOGGER.debug(msg.format(self, reason.getErrorMessage()))
        self.__on_connection_lost(self, reason)

    def connect(self, host='127.0.0.1', port=5060):
        """Connects the client protocol.

        Keyword Arguments:
        host                   -- The remote host address to use for a client
                                  connection. Optional. Default: 127.0.0.1.
        port                   -- The remote host port to use for a client
                                  connection. Optional. Default: 5060.
        """

        msg = '{0} Connecting to host \'{1}:{2}\'...'
        LOGGER.debug(msg.format(self, host, port))

        self.__done = defer.Deferred()
        reactor.connectTCP(host, port, self, bindAddress=self.__clientaddr)
        return self.__done

    def disconnect(self):
        """Disconnects the client protocol.

        Returns:
        True on success. Otherwise, returns False.
        """

        msg = '{0} Attempting to destroy client connection...'.format(self)
        LOGGER.debug(msg)

        if not self.__protocol:
            msg = '{0} I don\'t have a client connection to destroy.'
            LOGGER.debug(msg.format(self))
            return False

        self.__protocol.disconnect()
        return True

    def __format__(self, format_spec):
        """Overrides default format handling for 'self'."""

        return '%s [%s]:' % (self.__class__.__name__, self.clientaddr)

    def __handle_client_state_change(self, reason):
        """Handles connection state changes.

        Keyword Arguments:
        reason                 -- The reason for the state change as a
                                  twisted.python.failure.Failure instance.
        """

        if self.__done is not None:
            if reason is None:
                self.__done.callback(self)
            else:
                self.__done.errback(self)
            self.__done = None

    def __on_client_connection_made(self):
        """Handles the connectionMade event from the client protocol."""

        msg = '{0} Client is done with connection attempt to host: \'{1}\''
        LOGGER.debug(msg.format(self, self.__protocol.host))
        self.__handle_client_state_change(None)

    @property
    def clientaddr(self):
        """Returns the client address."""

        return self.__clientaddr

    @property
    def client_id(self):
        """Returns the id for the client."""

        return self.__id

    @property
    def connecting(self):
        """Whether or not the the client is trying to establish a connection.

        Returns:
        True if the client is connecting. Otherwise, returns False.
        """

        if self.__failed:
            return False

        if self.__protocol is None:
            return True

        return self.__protocol.connection_state == ConnectionState.CONNECTING

    @property
    def connected(self):
        """Whether or not the client connection has been established.

        Returns:
        True if the client is connected. Otherwise, returns False.
        """

        if self.__protocol is None:
            return False

        return self.__protocol.connection_state == ConnectionState.CONNECTED


class TcpClientScenario(object):
    """The test scenario for testing SIP socket creation.

    This scenario confirms that Asterisk honors its tcpauthlimit property by
    trying to create more SIP sockets than the configuration specifies as the
    limit.
    """

    def __init__(self, scenario_id, host='127.0.0.1', port=5060,
                 allowed_connections=0):
        """Constructor.

        Keyword Arguments:
        scenario_id            -- The id for this scenario. Used for logging.
        host                   -- The remote host address to use for a client
                                  connection. Optional. Default: 127.0.0.1.
        port                   -- The remote host port to use for a client
                                  connection. Optional. Default: 5060.
        allowed_connections    -- The number of clients allowed by chan_sip.
                                  Optional. Default: 0.
        """

        self.__allowed_connections = allowed_connections
        self.__clients = None
        self.__connected_clients = None
        self.__host = host
        self.__iterator = None
        self.__port = port
        self.__on_complete = None
        self.__on_started = None
        self.__scenario_id = scenario_id
        self.__stopping = False

    def __disconnect_client(self, client):
        """Disconnects the given client.

        Keyword Arguments:
        client             -- The client to disconnect.

        Returns:
        The disconnected client.
        """

        if client is None and self.__stopping:
            return None

        msg = '{0} Disconnecting client [{1}]...'
        LOGGER.debug(msg.format(self, client.clientaddr))

        if not client.disconnect():
            self.__on_client_disconnect(client, None)
        return client

    def __evaluate_results(self, payload):
        """Evaluates the test scenario results.

        Keyword Arguments:
        payload                -- The event payload.
        """

        if self.finished:
            return payload

        msg = '{0} Evaluating scenario results...'.format(self)
        LOGGER.debug(msg)

        clients = sum(client.connected for client in self.__clients)
        self.__connected_clients = clients
        return payload

    def __format__(self, format_spec):
        """Overrides default format handling for 'self'."""

        return self.__class__.__name__ + ' [' + self.__scenario_id + ']:'

    def __get_next_client(self, client):
        """Tries to get the next client from the list.

        Keyword Arguments:
        client                 -- The current client.

        Returns:
        A client if the iteration is not complete. Else returns None.
        """

        client = None
        try:
            client = self.__iterator.next()
        except StopIteration:
            pass
        return client

    def __handle_state_change(self, sender):
        """Updates basic scenario state afer a client connection state change.

        Keyword Arguments:
        sender                 -- The client whose state has changed.

        Returns:
        True if the state was handled. Otherwise, returns False.
        """

        if sender is not None:
            if len(self.__clients) < sender.client_id:
                msg = '{0} Ruh-roh. I received an event for a client that I'
                msg += ' did not create.\n\t\tClient ID:\t{1}'
                LOGGER.warning(msg.format(self, sender.clientaddr))
                return True

        if self.__stopping:
            client = self.__get_next_client(sender)
            if client is None:
                if all(c.connected is False for c in self.__clients):
                    self.__report_results()
                    self.__reset_state()
            else:
                self.__disconnect_client(client)
            return True

        if self.finished:
            return True

        if not self.started:
            return False

        msg = '{0} All clients have finished connecting.'.format(self)
        LOGGER.debug(msg)
        self.__on_started.callback(self)
        return True

    def __initialize_clients(self):
        """Builds the SIP Client for this scenario.

        Returns:
        A list of n TcpClientFactory instances, where n equals
        self.__allowed_connections + 1.
        """

        clients = list()

        for i in range(0, self.__allowed_connections * 2):
            user = i + 2
            port = 5060 + user
            factory = TcpClientFactory(i,
                                       (self.__host, port),
                                       self.__on_client_disconnect)
            clients.append(factory)

        return clients

    def __on_client_connection_failure(self, reason):
        """Handles a client disconnect event.

        Keyword Arguments:
        reason                 -- The reason for the connection failure as a
                                  twisted.python.failure.Failure instance.
        """

        msg = '{0} Client connection failure: {1}.'
        LOGGER.debug(msg.format(self, reason.getErrorMessage()))
        self.__handle_state_change(None)

    def __on_client_disconnect(self, sender, payload):
        """Handles a client disconnect event.

        Keyword Arguments:
        sender                 -- The client that was disconnected.
        payload                -- The event payload.
        """

        msg = '{0} Client [{1}] is disconnected.'
        LOGGER.debug(msg.format(self, sender.clientaddr))
        self.__handle_state_change(sender)

    def __on_client_connecting_change(self, sender):
        """Handler for client connection state changes.

        Keyword Arguments:
        sender                 -- The client who sent the notification.
        payload                -- The event payload.
        """

        msg = '{0} Received a connection change notification from client [{1}].'
        LOGGER.debug(msg.format(self, sender.clientaddr))
        self.__handle_state_change(sender)

    def __report_results(self):
        """Logs the result of the scenario."""

        if not self.passed:
            msg = '{0} Scenario failed.\n'
            msg += '\tBased on the test configuration, I expected to receive:\n'
            msg += '\t\t{1} client connections.\n'
            msg += '\tHere is what I actually received:\n'
            msg += '\t\t{2} client connections.'
            LOGGER.error(msg.format(self,
                                    self.__allowed_connections,
                                    self.__connected_clients))
        else:
            LOGGER.info('{0} Congrats! The scenario passed.'.format(self))

        self.__on_complete.callback(self)

    def __reset_state(self):
        """Resets the scenario state."""

        self.__clients = None
        self.__iterator = None
        self.__on_complete = None
        self.__on_started = None
        self.__stopping = False

    def run(self):
        """Runs the SIP client scenario.

        Returns:
        A twisted.internet.defer.Deferred instance that can be used to
        determine when the scenario is complete.
        """

        LOGGER.debug('{0} Starting scenario...'.format(self))

        self.__setup_state()
        self.__start_clients()
        return self.__on_complete

    def __setup_state(self):
        """Sets up the state needed for this scenario to run."""

        self.__connected_clients = None
        self.__clients = self.__initialize_clients()
        self.__iterator = iter(self.__clients)

        self.__on_complete = defer.Deferred()
        self.__on_started = defer.Deferred()
        self.__on_started.addCallback(self.__evaluate_results)
        self.__on_started.addCallback(self.__teardown_state)

    def __start_clients(self):
        """Starts connection process for this scenario's clients."""

        msg = '{0} Attempting to connect {1} clients to Asterisk...'
        LOGGER.debug(msg.format(self, len(self.__clients)))

        deferreds = []
        for client in self.__clients:
            deferred = client.connect(self.__host, self.__port)
            if deferred is not None:
                deferred.addCallback(self.__on_client_connecting_change)
                deferred.addErrback(self.__on_client_connection_failure)
                deferreds.append(deferred)

    def __teardown_state(self, payload):
        """Disconnects the clients and resets the state.

        Keyword Arguments:
        payload                -- The event payload.
        """

        self.__stopping = True

        LOGGER.debug('{0} Tearing down the scenario...'.format(self))

        deferred = defer.Deferred()
        deferred.addCallback(self.__get_next_client)
        deferred.addCallback(self.__disconnect_client)
        deferred.callback(self)

        return payload

    @property
    def finished(self):
        """Whether or not the this scenario has finished execution.

        Returns:
        True if the scenario has finished execution. Otherwise, returns False.
        """

        return self.__connected_clients is not None

    @property
    def passed(self):
        """The results of the scenario.

        Returns:
        True if the scenario was successful. Otherwise, returns False.
        """

        if not self.finished:
            return False

        return self.__connected_clients == self.__allowed_connections

    @property
    def scenario_id(self):
        """Returns the id for this scenario."""

        return self.__scenario_id

    @property
    def started(self):
        """Returns a value indicating if this scenario has started."""

        if self.__clients is None:
            return False

        return all(c.connecting is False for c in self.__clients)
