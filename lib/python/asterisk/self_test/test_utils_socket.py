#!/usr/bin/env python
"""Utility module for socket handling

This module provides tests for the utils_socket module.

Copyright (C) 2018, Digium, Inc.
Kevin Harwell <kharwell@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
"""

from harness_shared import main
import unittest
from socket import SOCK_STREAM, SOCK_DGRAM, AF_INET, AF_INET6
from asterisk.utils_socket import Ports, PortError, get_available_port, MIN_PORT


class PortTests(unittest.TestCase):
    """Unit tests for port availability and reservations."""

    def setUp(self):
        self.ports = Ports()

    def _on_family(self, host, socktype, cb):
        host = host or ''

        if '.' in host:
            cb(host, socktype, AF_INET)
        elif ':' in host:
            cb(host, socktype, AF_INET6)
        else:
            for family in [AF_INET, AF_INET6]:
                cb(host, socktype, family)

    def _on_socktype(self, host, cb):
        for socktype in [SOCK_STREAM, SOCK_DGRAM]:
            self._on_family(host, socktype, cb)

    def _on_host(self, cb):
        self._on_socktype('', cb)

        for host in ['', '0.0.0.0', '127.0.0.1', '::', '::1']:
            self._on_socktype(host, cb)

    def test_001_reserve(self):
        """Test reserving ports for different families and types"""

        p = [51234, 51235]

        def reserve(h, s, f):
            self.ports.reserve(p, s, f)
        self._on_socktype(None, reserve)

        def test(h, s, f):
            self.assertEqual(self.ports.reserved_ports[s][f], p)
        self._on_socktype(None, test)

    def test_002_is_reserved(self):
        """Test if port is and is not reserved for families and types"""

        p = 51234

        def reserve(h, s, f):
            self.ports.reserve(p, s, f)
        self._on_socktype(None, reserve)

        self.assertTrue(self.ports.is_reserved(MIN_PORT - 1))

        def test(h, s, f):
            self.assertTrue(self.ports.is_reserved(p, s, f))
        self._on_socktype(None, test)

        def test2(h, s, f):
            self.assertFalse(self.ports.is_reserved(71234, s, f))
        self._on_socktype(None, test2)

    def test_003_get_avail(self):
        """Test retrieving a ports by families and types"""

        p = [0, 0]

        def test(h, s, f):
            self.assertNotEqual(self.ports.get_avail(h, p, s, f), p)
        self._on_host(test)

        p = [51234, 51235]

        def test2(h, s, f):
            self.assertEqual(self.ports.get_avail(h, p, s, f), p)
        self._on_host(test2)

        def reserve(h, s, f):
            self.ports.reserve(p, s, f)
        self._on_socktype(None, reserve)

        def test3(h, s, f):
            self.assertRaises(PortError, self.ports.get_avail, h, p, s, f)
        self._on_host(test3)

    def test_004_get_range(self):
        """Test retrieving a range of ports by families and types"""
        p = 0

        def test(h, s, f):
            self.assertEqual(len(self.ports.get_range(h, p, s, f, 3)), 3)
        self._on_host(test)

        p = 50000

        def test2(h, s, f):
            self.assertEqual(self.ports.get_range(h, p, s, f, 3),
                             [50000, 50001, 50002])
        self._on_host(test2)

        def test3(h, s, f):
            self.assertEqual(self.ports.get_range(h, p, s, f, -3),
                             [50000, 49999, 49998])
        self._on_host(test3)

    def test_005_get_range_and_reserve(self):
        """Test retrieving and reserving a range of ports by
        families and types"""
        p = 50000

        def get_range(h, s, f):
            self.ports.get_range_and_reserve(h, p, s, f, 3)
        self._on_socktype(None, get_range)

        def test(h, s, f):
            self.assertTrue(self.ports.is_reserved(50000, s, f))
        self._on_host(test)

        def test2(h, s, f):
            self.assertTrue(self.ports.is_reserved(50001, s, f))
        self._on_host(test2)

        def test3(h, s, f):
            self.assertTrue(self.ports.is_reserved(50002, s, f))
        self._on_host(test3)

    def test_006_get_available_port(self):
        """Test retrieving an available port"""
        p = 50000

        def test(h, s, f):
            self.assertEqual(get_available_port(h, s, f, 0, p), p)
        # Limit to single host since using global object
        self._on_socktype(None, test)

        p = 50001

        self.assertEqual(get_available_port(
            config={'-i': '0.0.0.0'}, num=2, port=p), p)
        self.assertEqual(get_available_port(
            config={'-i': '0.0.0.0',  '-t': ''}, num=2, port=p), p)
        self.assertEqual(get_available_port(
            config={'-i': '[::]'}, num=2, port=p), p)
        self.assertEqual(get_available_port(
            config={'-i': '[::]',  '-t': ''}, num=2, port=p), p)


if __name__ == "__main__":
    """Run the unit tests"""
    main()
