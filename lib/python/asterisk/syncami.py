#!/usr/bin/env python
"""AMI HTTP wrapper classes

Copyright (C) 2011, Digium, Inc.
Terry Wilson <twilson@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
"""

try:
    # python 2 import
    from urllib import urlencode
except:
    # python 3 import
    from urllib.parse import urlencode

from email.parser import HeaderParser
try:
    from httplib import *
except:
    from http.client import *


class InvalidAMIResponse(Exception):
    def __init__(self, response):
        self.response = response

    def __str__(self):
        return repr(self.response)


class SyncAMI(object):
    """A class for synchronously handling AMI actions and responses over HTTP

    It currently only raises an error on non-200 responses from the server. It
    would be a good idea to offer built-in checking of the Response header for
    non-success results, but this behavior differs between different versions
    of Asterisk, so for now we just return the response and can check the
    the Response header outside of the library. A login is attempted during
    construction."""

    def __init__(self, location="127.0.0.1:8088", path="/rawman",
                 username="user", secret="mysecret"):
        self.location = location
        self.path = path
        self.cookie = None
        try:
            self.con = HTTPConnection(location)
            self.login(username, secret)
        except:
            raise

    def login(self, username, secret):
        """Login to AMI

        Keyword Arguments:
        username The username to log into AMI with
        secret   The password for the user
        """
        return self.send({'action': 'login', 'username': username,
                          'secret': secret})

    def logoff(self):
        """Log out of AMI"""
        result = self.send({'action': 'logoff'})
        self.con.close()
        return result

    def send(self, args):
        """Send an AMI request "action" given a dict of header values

        Keyword Arguments:
        args    A dictionary of headers and values

        Returns:
        An email.message.Message which we could wrap with our own AMIMessage
        class if we were feeling industrious. You can get
        access the  headers via:
            ami = SyncAMI()
            res = ami.send({'action': 'ping'})
            res.items() => [("header", "value"), ...]
            res.get("header") => "value"
            res.get_all("header") => ["value", ...]
        """

        headers = {}
        params = "?" + urlencode(args)
        if self.cookie is not None:
            headers['Cookie'] = self.cookie
        self.con.request("GET", self.path + params, headers=headers)
        res = self.con.getresponse()
        if res.status != 200:
            raise InvalidAMIResponse(res)
        self.cookie = res.getheader('set-cookie', None)
        data = res.read().decode('utf-8')
        parser = HeaderParser()

        return parser.parsestr(data)
