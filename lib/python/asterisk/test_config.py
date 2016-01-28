#!/usr/bin/env python
"""Test configuration parsing and dependency checking

Copyright (C) 2011, Digium, Inc.
Russell Bryant <russell@digium.com>
Matt Jordan    <mjordan@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
"""

import sys
import os
import subprocess
import yaml
import socket
import traceback

sys.path.append("lib/python")

import test_suite_utils

from version import AsteriskVersion
from asterisk import Asterisk
from buildoptions import AsteriskBuildOptions
from sippversion import SIPpVersion


class TestConditionConfig(object):
    """This class creates a test condition config and will build up an
    object that derives from TestCondition based on that configuration
    """

    def __init__(self, config, definition, pre_post_type):
        """Construct a new test condition

        Keyword Arguments:
        config        The test condition specific configuration, from a
                      test-config.yaml file
        definition    The global type information, obtained from the global
                      test-config.yaml file
        pre_post_type 'pre' or 'post', depending on the type to build
        """
        self.pass_expected = True
        self.related_condition = ""
        self.type = pre_post_type.upper().strip()
        self.class_type_name = definition[self.type.lower()]['typename']
        self.enabled = True
        if 'related-type' in definition[self.type.lower()]:
            ppt_def = definition[self.type.lower()]
            self.related_condition = ppt_def['related-type'].strip()
        if 'enabled' in config:
            self.enabled = config['enabled']
        else:
            self.enabled = True
        self.expected_result = (config.get('expected_result') or
                                config.get('expectedResult') or
                                False)
        # Let non-standard configuration items be obtained from the
        # config object
        self.config = config

    def get_type(self):
        """The type of TestCondition (either PRE or POST)"""
        return self.type

    def get_related_condition(self):
        """The type name of the related condition that this condition uses"""
        return self.related_condition

    def make_condition(self):
        """Build and return the condition object defined by this config"""
        parts = self.class_type_name.split('.')
        module = '.'.join(parts[:-1])
        if module != '':
            mod = __import__(module)
            for comp in parts[1:]:
                mod = getattr(mod, comp)
            obj = mod(self)
            return obj
        return None


class Dependency(object):
    """Class that checks and stores the dependencies for a particular Test."""

    try:
        asterisk_build_options = AsteriskBuildOptions()
    except:
        asterisk_build_options = None

    try:
        ast = Asterisk()
    except:
        ast = None

    def __init__(self, dep):
        """Construct a new dependency

        Keyword arguments:
        dep A tuple containing the dependency type name and its subinformation.
        """

        self.name = ""
        self.version = ""
        self.met = False
        if "app" in dep:
            self.name = dep["app"]
            self.met = test_suite_utils.which(self.name) is not None
        elif "python" in dep:
            self.name = dep["python"]
            try:
                __import__(self.name)
                self.met = True
            except ImportError:
                pass
        elif "sipp" in dep:
            self.name = "SIPp"
            version = None
            feature = None
            if 'version' in dep['sipp']:
                version = dep['sipp']['version']
            if 'feature' in dep['sipp']:
                feature = dep['sipp']['feature']
            self.sipp_version = SIPpVersion()
            self.version = SIPpVersion(version, feature)
            if self.sipp_version >= self.version:
                self.met = True
            if self.version.tls and not self.sipp_version.tls:
                self.met = False
            if self.version.pcap and not self.sipp_version.pcap:
                self.met = False
        elif "custom" in dep:
            self.name = dep["custom"]
            method = "depend_%s" % self.name
            found = False
            for dir_method in dir(self):
                if dir_method == method:
                    self.met = getattr(self, dir_method)()
                    found = True
            if not found:
                print "Unknown custom dependency - '%s'" % self.name
        elif "asterisk" in dep:
            if self.ast:
                self.name = dep["asterisk"]
                self.met = self._find_asterisk_module(self.name)
            else:
                # Remote Asterisk instance. Assume dependency is met
                self.met = True
        elif "buildoption" in dep:
            if self.ast:
                self.name = dep["buildoption"]
                self.met = self._find_build_flag(self.name)
            else:
                # Remote Asterisk instance. Assume dependency is met
                self.met = True
        elif "pcap" in dep:
            self.name = "pcap"
            from test_case import PCAP_AVAILABLE
            self.met = PCAP_AVAILABLE
        else:
            print "Unknown dependency type specified:"
            for key in dep.keys():
                print key

    def depend_remote(self):
        """Check to see if we run against a remote instance of Asterisk"""
        test_config = TestConfig(os.getcwd())
        if not test_config.config:
            return False
        if test_config.config.get('asterisk-instances'):
            return True
        return False

    def depend_soundcard(self):
        """Check the soundcard custom dependency"""
        try:
            dsp_file = open("/dev/dsp", "r")
            dsp_file.close()
            return True
        except:
            return False

    def depend_ipv6(self):
        """Check the ipv6 custom dependency"""
        try:
            test_sock = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
            test_sock.close()
            return True
        except:
            return False

    def depend_ipv4addr(self):
        """Check that an interface has a bindable ipv4 address (not loopback)
        """
        if test_suite_utils.get_bindable_ipv4_addr():
            return True
        return False

    def depend_ipv6addr(self):
        """Check that an interface has a bindable ipv6 address (not loopback,
           not link-local)
        """
        if test_suite_utils.get_bindable_ipv6_addr():
            return True
        return False

    def depend_pjsuav6(self):
        """This tests if pjsua was compiled with IPv6 support.

        To do this, we run pjsua --help and parse the output to determine if
        --ipv6 is a valid option
        """
        if test_suite_utils.which('pjsua') is None:
            return False

        help_output = subprocess.Popen(['pjsua', '--help'],
                                       stdout=subprocess.PIPE).communicate()[0]
        if help_output.find('--ipv6') == -1:
            return False
        return True

    def depend_fax(self):
        """Checks if Asterisk contains the necessary modules for fax tests"""
        fax_providers = [
            "app_fax",
            "res_fax_spandsp",
            "res_fax_digium",
        ]

        for fax in fax_providers:
            if self._find_asterisk_module(fax):
                return True

        return False

    def depend_rawsocket(self):
        """Check the raw socket custom dependency"""
        try:
            test_sock = socket.socket(socket.AF_PACKET, socket.SOCK_RAW)
            test_sock.close()
            return True
        except:
            return False

    def _find_build_flag(self, name):
        """Determine if the specified build option exists"""
        if self.asterisk_build_options:
            return (self.asterisk_build_options.check_option(name))
        else:
            print "Unable to evaluate build options: no build options found"
            return False

    def _find_asterisk_module(self, name):
        """Determine if an Asterisk module exists"""
        if not Dependency.ast:
            print "Unable to evaluate Asterisk modules: Asterisk not found"
            return False

        if Dependency.ast.original_astmoddir == "":
            return False

        module = "%s/%s.so" % (Dependency.ast.original_astmoddir, name)
        if os.path.exists(module):
            return True

        return False


class TestConfig(object):
    """Class that contains the configuration for a specific test, as parsed
    by that tests test.yaml file.
    """

    def __init__(self, test_name, global_test_config=None):
        """Create a new TestConfig

        Keyword arguments:
        test_name The path to the directory containing the test-config.yaml
                  file to load
        """
        self.can_run = True
        self.test_name = test_name
        self.skip = None
        self.config = None
        self.summary = None
        self.description = None
        self.maxversion = []
        self.maxversion_check = False
        self.minversion = []
        self.minversion_check = False
        self.forced_version = None
        self.deps = []
        self.tags = []
        self.expect_pass = True
        self.excluded_tests = []
        self.features = set()
        self.feature_check = {}
        self.test_configuration = None
        self.condition_definitions = []
        self.global_test_config = global_test_config

        try:
            self._parse_config()
        except yaml.YAMLError as e:
            print("YAML Parse Error: %s" % e)
            print(traceback.format_exc())
            self.can_run = False
        except:
            print("Exception occurred while parsing config:", sys.exc_info()[0])
            print(traceback.format_exc())
            self.can_run = False

    def _process_global_settings(self):
        """Process settings in the top-level test-yaml config file"""

        if self.global_test_config is not None:
            settings = self.global_test_config
            self.condition_definitions = settings.condition_definitions
            self.forced_version = settings.forced_version
            return

        if "global-settings" in self.config:
            settings = self.config['global-settings']
            self.condition_definitions = settings.get('condition-definitions', [])
            self.test_configuration = settings.get('test-configuration')

            if self.test_configuration and self.test_configuration in self.config:
                self.config = self.config[self.test_configuration]

                if self.config is not None and 'exclude-tests' in self.config:
                    self.excluded_tests = self.config['exclude-tests']
            else:
                print ("WARNING - test configuration [%s] not found in "
                       "config file" % self.test_configuration)

    def _process_testinfo(self):
        """Process the test information block"""

        self.summary = "(none)"
        self.description = "(none)"
        if self.config is None:
            return
        if "testinfo" not in self.config:
            return
        testinfo = self.config["testinfo"]
        if "skip" in testinfo:
            self.skip = testinfo['skip']
            self.can_run = False
        if "summary" in testinfo:
            self.summary = testinfo["summary"]
        if "description" in testinfo:
            self.description = testinfo["description"]

    def _process_properties(self):
        """Process test properties block"""

        if self.config is None:
            return
        if "properties" not in self.config:
            return
        properties = self.config["properties"]
        minversion = properties.get("minversion", ["1.4"])

        if not isinstance(minversion, list):
            minversion = [minversion]
        self.minversion = [AsteriskVersion(ver) for ver in minversion]

        maxversion = properties.get("maxversion", [])
        if not isinstance(maxversion, list):
            maxversion = [maxversion]
        self.maxversion = [AsteriskVersion(ver) for ver in maxversion]

        self.expect_pass = (properties.get("expectedResult", self.expect_pass) and
                            properties.get("expected-result", self.expect_pass))
        if "tags" in properties:
            self.tags = properties["tags"]
        if "features" in properties:
            self.features = set(properties["features"])
        if "forced-version" in properties:
            self.forced_version = AsteriskVersion(properties["forced-version"])

        for ver in self.minversion:
            if ver.feature:
                self.features.add(ver.feature)

        for feature in self.features:
            self.feature_check[feature] = False

    def _parse_config(self):
        """Parse the test-config YAML file."""

        test_config = "%s/test-config.yaml" % self.test_name
        with open(test_config, "r") as config_file:
            self.config = yaml.load(config_file)

        if not self.config:
            print "ERROR: Failed to load configuration for test '%s'" % \
                self.test_name
            return

        self._process_global_settings()
        self._process_testinfo()
        self._process_properties()

    def get_conditions(self):
        """
        Gets the pre- and post-test conditions associated with this test

        Returns a list of 3-tuples containing the following:
            0: The actual condition object
            1: The condition type (either PRE or POST)
            2: The name of the related condition that this one depends on
        """
        conditions = []
        conditions_temp = []
        if (not self.config or 'properties' not in self.config
                or 'testconditions' not in self.config['properties']):
            return conditions

        for conf in self.config['properties'].get('testconditions'):
            matches = [cond_def for cond_def in self.condition_definitions
                       if cond_def['name'] == conf['name']]
            if len(matches) != 1:
                print ("Unknown or too many matches for condition: " +
                       conf['name'])
            else:
                pre_cond = TestConditionConfig(conf, matches[0], "Pre")
                post_cond = TestConditionConfig(conf, matches[0], "Post")
                conditions_temp.append(pre_cond)
                conditions_temp.append(post_cond)

        for cond in conditions_temp:
            cond_obj = (cond.make_condition(),
                        cond.get_type(),
                        cond.get_related_condition())
            conditions.append(cond_obj)

        return conditions

    def get_deps(self):
        """Get the dependencies for the test

        Raises ValueError if the 'properties' section is missing from the test
        configuration

        Returns:
        A list of Dependency objects
        """
        if not self.config:
            return []

        if not "properties" in self.config:
            raise ValueError("%s: Missing properties section" % self.test_name)

        if not self.deps:
            self.deps = [
                Dependency(dep)
                for dep in self.config["properties"].get("dependencies") or []
            ]
        return self.deps

    def check_deps(self, ast_version):
        """Check whether or not a test should execute based on its dependencies

        Keyword arguments:
        ast_version The AsteriskVersion object containing the version of
                    Asterisk that will be executed
        Returns:
        can_run True if the test can execute, False otherwise
        """

        if not self.config:
            return False

        if self.forced_version is not None:
            ast_version = self.forced_version

        # If we have a minimum version for our branch; use that. Otherwise,
        # compare against all listed minimum versions.
        min_candidates = [ver for ver in self.minversion
                          if ver.major == ast_version.major]
        if not len(min_candidates):
            min_candidates = self.minversion
        self.minversion_check = all([ast_version >= ver
                                     for ver in min_candidates])
        # Max version is a bit different: generally, it is a hard cut-off
        # (as what the test covers has been removed). We should always be less
        # than any provided max version.
        self.maxversion_check = all([ast_version < ver
                                     for ver in self.maxversion])

        if not self.minversion_check or not self.maxversion_check:
            self.can_run = False

        for feature in self.features:
            self.feature_check[feature] = ast_version.has_feature(feature)
            if not self.feature_check[feature]:
                self.can_run = False

        for dep in self.get_deps():
            if dep.met is False:
                self.can_run = False
        return self.can_run

    def check_tags(self, requested_tags):
        """Check whether or not a test should execute based on its tags

        Keyword arguments:
        requested_tags The list of tags used for selecting a subset of
                       tests.  The test must have all tags to run.
        Returns:
        can_run True if the test can execute, False otherwise
        """

        if not self.config:
            return False

        # If no tags are requested, this test's tags don't matter
        if not requested_tags:
            return self.can_run

        intersection = set(requested_tags).intersection(set(self.tags))
        if len(intersection) == 0:
            self.can_run = False

        # all tags matched successfully
        return self.can_run
