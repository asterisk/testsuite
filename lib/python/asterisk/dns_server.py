#!/usr/bin/env python
""" Pluggable module for running an isolated configured DNS server

Copyright (C) 2015, Digium, Inc.
Joshua Colp <jcolp@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
"""

import logging

from twisted.internet import reactor
from twisted.names import server, authority, dns

LOGGER = logging.getLogger(__name__)


class DNSServer(object):
    """Start a local DNS server instance using twisted-names with provided zones.

    Configuration options include:
        port: The port to listen for DNS requests on.
            defaults to 10053.
        python-zones: An array of Python zone files.
        bind-zones: An array of BIND zone files.

    Python zone files are defined using python source code. An example is present
    at https://twistedmatrix.com/documents/current/names/howto/names.html

    BIND zone files are defined in BIND-syntax style.
    """
    def __init__(self, config, test_obj):
        """Initialize and configure the DNS object."""

	zones = []
	port = config.get('port', 10053)
	pyzones = config.get('python-zones', [])
	bindzones = config.get('bind-zones', [])

	for pyzone in pyzones:
		zones.append(authority.PySourceAuthority('%s/dns_zones/%s' % (test_obj.test_name, pyzone)))
		LOGGER.info("Added Python zone file %s" % (pyzone))

	for bindzone in bindzones:
		zones.append(authority.BindAuthority('%s/dns_zones/%s' % (test_obj.test_name, bindzone)))
		LOGGER.info("Added BIND zone file %s" % (bindzone))

	factory = server.DNSServerFactory(authorities=zones)
	protocol = dns.DNSDatagramProtocol(controller=factory)

	reactor.listenUDP(port, protocol)
	reactor.listenTCP(port, factory)

	LOGGER.info("Started DNS server (UDP and TCP) on port %d" % (port))
