"""Asterisk testsuite utils

This module provides access to Asterisk testsuite utility
functions from within python code.

Copyright (C) 2010, Digium, Inc.
Paul Belanger <pabelanger@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
"""

import os
import logging
import re
import sys

from os import close
from os import remove
from shutil import move
from tempfile import mkstemp
from .config import ConfigFile

LOGGER = logging.getLogger(__name__)


if sys.version_info[0] == 3:
    unicode = str

def which(program):
    """Find the executable for a specified program

    Taken from:
    http://stackoverflow.com/questions/377017/test-if-executable-exists-in-python
    """
    def is_exe(fpath):
        """Is this an executable?"""
        return os.path.exists(fpath) and os.access(fpath, os.X_OK)

    fpath, fname = os.path.split(program)
    if fpath:
        if is_exe(program):
            return program

    else:
        for path in os.environ["PATH"].split(os.pathsep):
            exe_file = os.path.join(path, program)
            if is_exe(exe_file):
                return exe_file

    return None


def file_replace_string(file_name, pattern, subst):
    """Replace strings within a file with substr.

    Keyword arguments:
    file_name    filename of the text file within which strings are meant
                 to be replaced
    pattern      string in file which is matched against, removed, and
                 replaced by substr
    subst        string which is substituted for the pattern once the operation
                 is finished
    """
    # Create temp file
    f_handle, abs_path = mkstemp()
    new_file = open(abs_path, 'w')
    old_file = open(file_name)
    for line in old_file:
        new_file.write(line.replace(pattern, subst))
    # Close temp file
    new_file.close()
    close(f_handle)
    old_file.close()
    # Remove original file
    remove(file_name)
    # Move new file
    move(abs_path, file_name)


def all_match(pattern, message):
    """Match all items in a pattern to some message values

    This will recursively call itself, matching each item in pattern
    to the items in message

    :param pattern: Configured pattern.
    :param message: Message to compare.
    :returns: True if message matches pattern; False otherwise.
    """
    if isinstance(message, bytes) or isinstance(message, bytearray):
        # bytes need to be decoded as the yaml config assumes string-like objects
        message = message.decode('utf-8')
    LOGGER.debug('Pattern: %s, message %s' % (str(pattern), str(message)))
    if pattern is None:
        # Empty pattern always matches
        return True
    elif isinstance(pattern, list):
        # List must be an exact match
        res = len(pattern) == len(message)
        i = 0
        while res and i < len(pattern):
            res = all_match(pattern[i], message[i])
            i += 1
        return res
    elif isinstance(pattern, dict):
        # Dict should match for every field in the pattern.
        # extra fields in the message are fine.
        for key, value in pattern.items():
            to_check = message.get(key)
            if to_check is None or not all_match(value, to_check):
                return False
        return True
    elif isinstance(pattern, str) or isinstance(pattern, unicode):
        # Pattern strings are considered to be regexes
        return re.match(pattern, str(message)) is not None
    elif isinstance(pattern, int):
        # Integers are literal matches
        return pattern == message
    else:
        LOGGER.error("Unhandled pattern type %s" % type(pattern))


def get_bindable_ipv4_addr():
    """Attempts to obtain a bindable IPv4 address that isn't loopback
    """
    try:
        import netifaces
    except:
        return None

    interfaces = netifaces.interfaces()
    for interface in interfaces:
        ifaddresses = netifaces.ifaddresses(interface)
        ifaddress4 = ifaddresses.get(netifaces.AF_INET)

        if not ifaddress4:
            continue

        for address in ifaddress4:
            if address.get('broadcast'):
                return address.get('addr')

    return None


def get_bindable_ipv6_addr():
    """Attempts to obtain a bindable IPv6 address that isn't loopback
    or link local
    """
    try:
        import netifaces
    except:
        return None

    interfaces = netifaces.interfaces()
    for interface in interfaces:
        ifaddresses = netifaces.ifaddresses(interface)
        ifaddress6 = ifaddresses.get(netifaces.AF_INET6)

        if not ifaddress6:
            continue

        for address in ifaddress6:
            addr = address.get('addr')
            if not addr:
                continue

            # skip anything containing zone marker (link local)
            if '%' in addr:
                continue

            #skip loopback address
            if addr == '::1':
                continue

            return addr

    return None

def get_asterisk_conf():
    localtest_root = os.getenv("AST_TEST_ROOT")
    if localtest_root:
        # The default etc directory for Asterisk
        default_etc_directory = os.path.join(localtest_root, "etc/asterisk")
    else:
        # The default etc directory for Asterisk
        default_etc_directory = "/etc/asterisk"

    # Find the system installed asterisk.conf
    ast_confs = [
        os.path.join(default_etc_directory, "asterisk.conf"),
        "/usr/local/etc/asterisk/asterisk.conf",
    ]
    _ast_conf = None
    for config in ast_confs:
        if os.path.exists(config):
            _ast_conf = ConfigFile(config)
            break
    if _ast_conf is None:
        msg = "Unable to locate asterisk.conf in any known location"
        LOGGER.error(msg)
        raise Exception(msg)

    # Get the Asterisk directories from the Asterisk config file
    _ast_conf.directories = {};
    for cat in _ast_conf.categories:
        if cat.name == "directories":
            for (var, val) in cat.options:
                _ast_conf.directories[var] = val

    return _ast_conf
