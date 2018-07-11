"""SIPp Version String Handling

Copyright (C) 2010, Digium, Inc.
Paul Belanger <pabelanger@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
"""

import subprocess
from . import test_suite_utils


class SIPpVersion:
    """A SIPp Version.

    """
    def __init__(self, version=None, feature=None):
        """Construct a SIPp Version parser.

        Keyword Arguments:
        version The SIPp version string to parse.
        """
        self.version_str = None
        self.feature_str = None
        self.concept = None
        self.major = None
        self.minor = None
        self.tls = False
        self.pcap = False

        if version is None and feature is None:
            sipp = test_suite_utils.which("sipp")
            if sipp is None:
                return

            cmd = [
                sipp, "-v"
            ]
            try:
                sipp_process = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                                stderr=subprocess.STDOUT)
            except OSError:
                return
            for line in sipp_process.stdout:
                line = line.decode('utf-8').strip()
                if line.startswith('SIPp '):
                    sipp = line[5:]
                    sipp = sipp.split(',', 1)
                    sipp = sipp[0].split('-', 1)
                    version = sipp[0]
                    if len(sipp) > 1:
                        feature = sipp[1]
            sipp_process.wait()

        if version is not None:
            self.__parse_version(version)
        if feature is not None:
            self.__parse_feature(feature)

    def __str__(self):
        """String representation of the SIPp version"""
        res = ''
        if self.version_str is not None:
            res = self.version_str
        if self.feature_str is not None:
            res = "%s-%s" % (res, self.feature_str)

        return res.strip('-')

    def __int__(self):
        """Return the version as an integer value

        This allows for comparisons between SIPp versions"""
        res = 0
        if self.concept is not None:
            res = int(self.concept.strip('v')) * 10000000
        if self.major is not None:
            res += int(self.major) * 100000
        if self.minor is not None:
            res += int(self.minor) * 1000

        return res

    def __cmp__(self, other):
        """Compare two SIPpVersion instances against each other"""
        return (int(self) > int(other)) - (int(self) < int(other))

    def __ne__(self, other):
        """Determine if this SIPpVersion instance is not equal to another"""
        res = self.__cmp__(other)
        if ((res == 0) and (self.tls or self.pcap or other.tls or other.pcap)):
            if (self.tls == other.pcap) or (self.pcap == other.tls):
                return True
            return False
        return res

    def __eq__(self, other):
        """Determine if this SIPpVersion instance is equal to another"""
        res = self.__cmp__(other)
        if ((res == 0) and (self.tls == other.tls and self.pcap == other.pcap)):
                return True
        return False

    def __le__(self, other):
        """Determine if this SIPpVersion instance is less than or equal to another"""
        return int(self) <= int(other)

    def __lt__(self, other):
        """Determine if this SIPpVersion instance is less than another"""
        return int(self) < int(other)

    def __parse_version(self, version):
        """Parse the version string returned from SIPp"""
        self.version_str = version
        if version is not None:
            parts = self.version_str.split(".")
            self.concept = parts[0]
            self.major = parts[1]
            self.minor = None
            if len(parts) >= 3:
                self.minor = parts[2]

    def __parse_feature(self, value):
        """Parse the features supported by this SIPp install"""
        self.feature_str = value
        if value.find("TLS") > -1:
            self.tls = True
        if value.find("PCAP") > -1:
            self.pcap = True
