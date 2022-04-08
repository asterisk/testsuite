"""Utility module for socket handling

This module provides classes and wrappers around the socket library.

Copyright (C) 2018, Digium, Inc.
Kevin Harwell <kharwell@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
"""

import logging

from socket import *


LOGGER = logging.getLogger(__name__)

# Number of times to try and find an available (non-reserved and unused) port
PORT_ATTEMPTS = 100

# Don't allow any port to be retrieved and reserved below this value
MIN_PORT = 10000


def socket_type(socktype):
    """Retrieve a string representation of the socket type."""
    return {
        SOCK_STREAM: 'TCP',
        SOCK_DGRAM: 'UDP',
    }.get(socktype, 'Unknown Type')


def socket_family(family):
    """Retrieve a string representation of the socket family."""
    return {
        AF_INET: 'IPv4',
        AF_INET6: 'IPv6',
    }.get(family, 'Unknown Family')


def get_resolved(host='', family=None):
    """Get and/or validate the family and host and/or resolve it"""

    def get_family(h, f):
        try:
            inet_pton(f, h)
            return f
        except:
            return None

    if not host:
        return ('', family or AF_INET)

    host = host.lstrip('[').rstrip(']')

    if family == None:
        family = get_family(host, AF_INET) or get_family(host, AF_INET6)

        if family:
            # host is already an ip address, so go ahead and return
            return (host, family)

    if family == None:
        family = AF_INET

    try:
        host = getaddrinfo(host, None, family)[0][4][0]
    except:
        raise ValueError("Unable to resolve host '{0}' ({1}) ".format(
            host, socket_family(family)))

    return (host, family)


def get_unused_os_port(host='', port=0, socktype=SOCK_STREAM, family=AF_INET):
    """Retrieve an unused port from the OS.

    Host can be an empty string, or a specific address. However, if an address
    is specified the family must coincide with the address or an exception is
    thrown. For example:

    host='', family=<either AF_INET or AF_INET6>
    host='0.0.0.0', family=AF_INET
    host='127.0.0.1', family=AF_INET
    host='::', family=AF_INET6
    host='::1', family=AF_INET6

    If the given port is equal to zero then an available port is chosen by the
    operating system and returned. If a number greater than zero is given for
    the port, then this checks if that port is currently not in use (from the
    operating system's perspective). If unused then it's returned. Zero is
    returned if a port is unavailable.

    Keyword Arguments:
    host - The host address
    port - Port number to check availability
    socktype - socket types (SOCK_STREAM, SOCK_DGRAM, etc.)
    family - protocol family (AF_INET, AF_INET6, etc.)

    Return:
    A usable port, or zero if a port is unavailable.
    """

    host = host.lstrip('[').rstrip(']')

    res = 0
    s = socket(family, socktype)
    try:
        if socktype == SOCK_STREAM:
            s.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)

        s.bind((host, port))
        res = s.getsockname()[1]
    except error as e:
        # errno = 98 is 'Port already in use'. However, if any error occurs
        # just fail since we probably don't want to bind to it anyway.
        LOGGER.debug("{0}/{1} port '{2}' is in use".format(
            socket_type(socktype), socket_family(family), port))

    s.close()
    return res


class PortError(ValueError):
    """Error raised when the number of attempts to find an available
    port is exceeded"""

    def __init__(self, socktype, family, port=0, attempts=PORT_ATTEMPTS):
        """Create a port error"""
        if port:
            msg = "{0}/{1} port '{2}' not available ".format(
                socket_type(socktype), socket_family(family), port)
        else:
            msg = "Unable to get usable {0}/{1} port after {2} attempts".format(
                socket_type(socktype), socket_family(family), attempts)
        super(ValueError, self).__init__(msg)


class Ports(object):
    """An interface for port availability. Handles retrieving vacant ports,
    and also guarantees returned ports are not used by others by adding it to,
    and maintaining a container of reserved ports. The internal container is
    a list of ports stored by socket types and family:

    ports[socktype][family] = [<ports>]

    The ports stored here represent ports that are considered unavailable and
    should not be bound to.
    """

    def __init__(self):
        """Create a reserved ports container."""
        self.reserved_ports = {}

    def reserve(self, ports, socktype=SOCK_STREAM, family=AF_INET):
        """Mark the given ports as reserved. Meaning that even if the operating
        system has these ports as free they'll be considered unusable if set as
        reserved.

        Keyword Arguments:
        ports - A list of ports to reserve
        socktype - socket types (SOCK_STREAM, SOCK_DGRAM, etc.)
        family - protocol family (AF_INET, AF_INET6, etc.)
        """

        if isinstance(ports, int):
            ports = [ports]
        if not isinstance(ports, list):
            ports = list(ports)

        if socktype not in self.reserved_ports:
            self.reserved_ports[socktype] = {}

        if family not in self.reserved_ports[socktype]:
            self.reserved_ports[socktype][family] = ports
        else:
            self.reserved_ports[socktype][family].extend(ports)

    def is_reserved(self, port, socktype=SOCK_STREAM, family=AF_INET):
        """Check to see if a given port is reserved.

        Keyword Arguments:
        port - The port to check
        socktype - socket types (SOCK_STREAM, SOCK_DGRAM, etc.)
        family - protocol family (AF_INET, AF_INET6, etc.)

        Return:
        True if the port is reserved, False otherwise
        """

        try:
            if (port < MIN_PORT or
                    port in self.reserved_ports[socktype][family]):

                LOGGER.debug("{0}/{1} port '{2}' is reserved".format(
                    socket_type(socktype), socket_family(family), port))
                return True
        except:
            pass

        return False

    def get_avail(self, host='', ports=0, socktype=SOCK_STREAM, family=AF_INET,
                  attempts=PORT_ATTEMPTS):
        """Retrieve available ports. Ports are considered available if they
        have not been reserved and are currently not in use by something else.

        If a given port is zero this function retrieves an available port from
        the operating system. If non-zero it checks to make sure the port is
        currently unused by the operating system.

        Once retrieved or validated it makes sure the port has not already been
        reserved. If it is reserved and port was initially zero it tries again
        up to 'attempts' tries. Otherwise if it was non-zero an exception is
        thrown.

        Keyword Arguments:
        host - host address
        port - port number(s) to check availability
        socktype - socket types (SOCK_STREAM, SOCK_DGRAM, etc.)
        family - protocol family (AF_INET, AF_INET6, etc.)
        attempts - The number of attempts to try and find a free port

        Return:
        Available ports as a list, otherwise a PortError exception is thrown
        if none are available.
        """

        if isinstance(ports, int):
            ports = [ports]
        if not isinstance(ports, list):
            ports = list(ports)

        LOGGER.debug("Checking the following {0}/{1} ports for availability: "
            "{2}".format(socket_type(socktype), socket_family(family), ports))

        res = []
        for port in ports:
            for attempt in range(attempts):
                p = get_unused_os_port(host, port, socktype, family)
                if p != 0 and not self.is_reserved(p, socktype, family):
                    res.append(p)
                    break

                if port:
                    raise PortError(socktype, family, port)
            else:
                raise PortError(socktype, family, attempts=attempts)

        return res

    def get_range(self, host='', port=0, socktype=SOCK_STREAM,
                  family=AF_INET, num=1, attempts=PORT_ATTEMPTS):
        """Retrieve a range of ports starting at port.

        Keyword Arguments:
        host - host address
        port - port number to get and/or check availability
        socktype - socket types (SOCK_STREAM, SOCK_DGRAM, etc.)
        family - protocol family (AF_INET, AF_INET6, etc.)
        num - the number of ports to return including a given port
        attempts - The number of attempts to try and find a free port

        Return:
        A list of available port(s). If none are available then a PortError
        exception is thrown.
        """

        num = num or 1

        for attempt in range(attempts):
            step = 1 if num > 0 else -1
            if port != 0:
                return self.get_avail(
                    host, range(port, port + num, step),
                    socktype, family, attempts)

            # Need a random port first
            avail = self.get_avail(host, 0, socktype, family)

            if abs(num) <= 1:
                return avail

            try:
                avails = self.get_avail(
                    host, range(avail[0] + step, avail[0] + num, step),
                    socktype, family, attempts)
            except PortError:
                # At least one port not free, try again
                continue

            return avail + avails

        raise PortError(socktype, family, attempts=attempts)

    def get_range_and_reserve(self, host='', port=0, socktype=SOCK_STREAM,
                              family=AF_INET, num=0, attempts=PORT_ATTEMPTS):
        """Retrieve available port and port +/- num and reserve them.

        If any ports are returned by calling 'get_range' those ports are then
        stored as 'reserved'.

        Keyword Arguments:
        host - host address
        port - port number to check availability
        socktype - socket types (SOCK_STREAM, SOCK_DGRAM, etc.)
        family - protocol family (AF_INET, AF_INET6, etc.)
        num - the number of ports to num +/- port
        attempts - The number of attempts to try and find a free port

        Return:
        If available, return the port +/- num ports, otherwise return an
        empty list.
        """

        res = self.get_range(host, port, socktype, family, num, attempts)
        self.reserve(res, socktype, family)
        return res


PORTS = Ports()


def get_available_port(host='', port=0, socktype=SOCK_DGRAM,
                       family=None, num=0):
    """Retrieve the primary available port, and reserve it and its offsets.

    The majority of use cases probably involve the need to reserve multiple
    ports (primary plus some offsets), but only retrieve the primary port.
    This function does that.

    This function purposely throws an exception if it cannot locate a
    singular port.

    Note:
    This is a wrapper/convenience function. See the
    Ports.get_range_and_reserve method for more functional details.

    Result:
    The singular primary available port.
    """

    host, family = get_resolved(host, family)

    available = PORTS.get_range_and_reserve(
        host, port, socktype, family, num)
    # If we don't have a valid socktype and family badness happens
    return available[0]
