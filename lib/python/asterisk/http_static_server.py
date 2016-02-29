#!/usr/bin/env python
"""Pluggable module for running an HTTP server that hosts static content

Copyright (C) 2016, Digium, Inc.
Matt Jordan <mjordan@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
"""

import os

from twisted.internet import reactor
from twisted.web import static, server

class HTTPStaticServer(object):
    """A pluggable module that creates an HTTP server hosting static content
    """

    def __init__(self, module_config, test_object):
        """Constructor

        Keyword Arguments:
        module_config The pluggable module's configuration
        test_object   The one and only test object
        """
        root = static.File(os.path.join(os.getcwd(),
                                        module_config['root-directory']))
        reactor.listenTCP(module_config.get('port', 80), server.Site(root))
