#!/usr/bin/env python
'''Asterisk external test suite driver.

Copyright (C) 2011, Digium, Inc.
Russell Bryant <russell@digium.com>
Matt Jordan    <mjordan@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
'''

import sys
import os
import subprocess
import yaml
import socket

sys.path.append("lib/python")

import TestSuiteUtils

from version import AsteriskVersion
from asterisk import Asterisk
from buildoptions import AsteriskBuildOptions
from sippversion import SIPpVersion

class TestConditionConfig:
    """
    This class creates a test condition config and will build up an
    object that derives from TestCondition based on that configuration
    """

    def __init__(self, config, definition, pre_post_type):
        """
        Construct a new test condition

        config - the test condition specific configuration, from a test-config.yaml file
        definition - the global type information, obtained from the global test-config.yaml file
        pre_post_type - 'pre' or 'post', depending on the type to build
        """
        self.passExpected = True
        self.relatedCondition = ""
        self.type = pre_post_type.upper().strip()
        self.classTypeName = definition[pre_post_type.lower()]['typename']
        self.enabled = True
        if 'related-type' in definition[pre_post_type.lower()]:
            self.relatedCondition = definition[pre_post_type.lower()]['related-type'].strip()
        if 'enabled' in config:
            if config ['enabled'].upper().strip() == 'FALSE':
                self.enabled = False
        if 'expectedResult' in config:
            try:
                self.passExpected = not (config["expectedResult"].upper().strip() == "FAIL")
            except:
                self.passExpected = False
                print "ERROR: '%s' is not a valid value for expectedResult" % config["expectedResult"]
        """ Let non-standard configuration items be obtained from the config object """
        self.config = config

    def get_type(self):
        """
        The type of TestCondition (either PRE or POST)
        """
        return self.type

    def get_related_condition(self):
        """
        The type name of the related condition that this condition will use
        """
        return self.relatedCondition

    def make_condition(self):
        """
        Build up and return the condition object defined by this configuration
        """
        parts = self.classTypeName.split('.')
        module = ".".join(parts[:-1])
        if module != "":
            m = __import__(module)
            for comp in parts[1:]:
                m = getattr(m, comp)
            obj = m(self)
            return obj
        return None


class SkipTest:
    def __init__(self, skip):
        self.name = ""
        self.met = True
        if "branch" in skip:
            self.name = skip["branch"]
            tmp = "%s-%s-%s" % ("SVN-branch", skip["branch"], "r12345")
            ast_version = AsteriskVersion()
            version = AsteriskVersion(tmp)
            if ast_version.is_same_branch(version):
                self.met = False


class Dependency:
    """
    This class checks and stores the dependencies for a particular Test.
    """

    __asteriskBuildOptions = AsteriskBuildOptions()

    __ast = Asterisk()

    def __init__(self, dep):
        """
        Construct a new dependency

        Keyword arguments:
        dep -- A tuple containing the dependency type name and its subinformation.
        """

        self.name = ""
        self.version = ""
        self.met = False
        if "app" in dep:
            self.name = dep["app"]
            self.met = TestSuiteUtils.which(self.name) is not None
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
            for m in dir(self):
                if m == method:
                    self.met = getattr(self, m)()
                    found = True
            if not found:
                print "Unknown custom dependency - '%s'" % self.name
        elif "asterisk" in dep:
            self.name = dep["asterisk"]
            self.met = self.__find_asterisk_module(self.name)
        elif "buildoption" in dep:
            self.name = dep["buildoption"]
            self.met = self.__find_build_flag(self.name)
        elif "pcap" in dep:
            self.name = "pcap"
            from TestCase import PCAP_AVAILABLE
            self.met = PCAP_AVAILABLE
        else:
            print "Unknown dependency type specified:"
            for key in dep.keys():
                print key

    def depend_soundcard(self):
        """
        Check the soundcard custom dependency
        """
        try:
            f = open("/dev/dsp", "r")
            f.close()
            return True
        except:
            return False

    def depend_ipv6(self):
        """
        Check the ipv6 custom dependency
        """
        try:
            s = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
            s.close()
            return True
        except:
            return False

    def depend_pjsuav6(self):
        '''
        This tests if pjsua was compiled with IPv6 support. To do this,
        we run pjsua --help and parse the output to determine if --ipv6
        is a valid option
        '''
        if TestSuiteUtils.which('pjsua') is None:
            return False

        help_output = subprocess.Popen(['pjsua', '--help'],
                                       stdout=subprocess.PIPE).communicate()[0]
        if help_output.find('--ipv6') == -1:
            return False
        return True

    def depend_fax(self):
        """
        Checks if Asterisk contains the necessary modules for fax tests
        """
        fax_providers = [
            "app_fax",
            "res_fax_spandsp",
            "res_fax_digium",
        ]

        for f in fax_providers:
            if self.__find_asterisk_module(f):
                return True

        return False

    def __find_build_flag(self, name):
        return (self.__asteriskBuildOptions.checkOption(name))

    def __find_asterisk_module(self, name):
        if "astmoddir" not in Dependency.__ast.directories:
            return False

        module = "%s/%s.so" % (Dependency.__ast.directories["astmoddir"], name)
        if os.path.exists(module):
            return True

        return False


class TestConfig:
    """
    Class that contains the configuration for a specific test, as parsed
    by that tests test.yaml file.
    """

    def __init__(self, test_name, global_test_config = None):
        """
        Create a new TestConfig

        Keyword arguments:
        test_name -- The path to the directory containing the test-config.yaml file to load
        """
        self.can_run = True
        self.test_name = test_name
        self.skip = None
        self.config = None
        self.summary = None
        self.maxversion = None
        self.maxversion_check = False
        self.minversion = None
        self.minversion_check = False
        self.deps = []
        self.skips = []
        self.tags = []
        self.expectPass = True
        self.excludedTests = []
        self.test_configuration = "(none)"
        self.condition_definitions = []
        self.global_test_config = global_test_config
        self.__parse_config()

    def __process_global_settings(self):
        """
        These settings only apply to the 'global' test-yaml config file.  If we were passed in
        the global settings, grab what we need and return
        """
        if self.global_test_config != None:
            self.condition_definitions = self.global_test_config.condition_definitions
            return

        if "global-settings" in self.config:
            global_settings = self.config['global-settings']
            if "condition-definitions" in global_settings:
                self.condition_definitions = global_settings['condition-definitions']
            if "test-configuration" in global_settings:
                self.test_configuration = global_settings['test-configuration']
                if self.test_configuration in self.config:
                    self.config = self.config[self.test_configuration]

                    if self.config != None and 'exclude-tests' in self.config:
                        self.excludedTests = self.config['exclude-tests']
                else:
                    print "WARNING - test configuration [%s] not found in config file" % self.test_configuration

    def __process_testinfo(self):
        self.summary = "(none)"
        self.description = "(none)"
        if self.config == None:
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

    def __process_properties(self):
        self.minversion = AsteriskVersion("1.4")
        if self.config == None:
            return
        if "properties" not in self.config:
            return
        properties = self.config["properties"]
        if "minversion" in properties:
            try:
                self.minversion = AsteriskVersion(properties["minversion"])
            except:
                self.can_run = False
                print "ERROR: '%s' is not a valid minversion" % \
                        properties["minversion"]
        if "maxversion" in properties:
            try:
                self.maxversion = AsteriskVersion(properties["maxversion"])
            except:
                self.can_run = False
                print "ERROR: '%s' is not a valid maxversion" % \
                        properties["maxversion"]
        if "expectedResult" in properties:
            try:
                self.expectPass = not (properties["expectedResult"].upper().strip() == "FAIL")
            except:
                self.can_run = False
                print "ERROR: '%s' is not a valid value for expectedResult" %\
                        properties["expectedResult"]
        if "tags" in properties:
            self.tags = properties["tags"]
        if "skip" in properties:
            self.skip = properties["skip"]

    def __parse_config(self):
        test_config = "%s/test-config.yaml" % self.test_name
        try:
            f = open(test_config, "r")
        except IOError:
            print "Failed to open %s" % test_config
            return
        except:
            print "Unexpected error: %s" % sys.exc_info()[0]
            return

        self.config = yaml.load(f)
        f.close()

        if not self.config:
            print "ERROR: Failed to load configuration for test '%s'" % \
                    self.test_name
            return

        self.__process_global_settings()
        self.__process_testinfo()
        self.__process_properties()

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
        if not self.config or 'properties' not in self.config or 'testconditions' not in self.config['properties']:
            return conditions

        for c in self.config['properties'].get('testconditions'):
            matched_definition = [d for d in self.condition_definitions if d['name'] == c['name']]
            if len(matched_definition) != 1:
                print "Unknown or too many matches for condition: " + c['name']
            else:
                pre_cond = TestConditionConfig(c, matched_definition[0], "Pre")
                post_cond = TestConditionConfig(c, matched_definition[0], "Post")
                conditions_temp.append(pre_cond)
                conditions_temp.append(post_cond)

        for cond in conditions_temp:
            c = cond.make_condition(), cond.get_type(), cond.get_related_condition()
            conditions.append(c)

        return conditions

    def check_deps(self, ast_version):
        """
        Check whether or not a test should execute based on its configured dependencies

        Keyword arguments:
        ast_version -- The AsteriskVersion object containing the version of Asterisk that
            will be executed
        returns can_run - True if the test can execute, False otherwise
        """

        if not self.config:
            return False

        self.deps = [
            Dependency(d)
                for d in self.config["properties"].get("dependencies") or []
        ]

        self.minversion_check = True
        if ast_version < self.minversion:
            self.can_run = False
            self.minversion_check = False
            return self.can_run

        self.maxversion_check = True
        if self.maxversion is not None and ast_version > self.maxversion:
            self.can_run = False
            self.maxversion_check = False
            return self.can_run

        for d in self.deps:
            if d.met is False:
                self.can_run = False
                break
        return self.can_run

    def check_skip(self, ast_version):
        if not self.config:
            return False

        self.skips = [
            SkipTest(s)
                for s in self.config["properties"].get("skip") or []
        ]

        self.can_run = all([s.met for s in self.skips if s.met is False])
        return self.can_run

    def check_tags(self, requested_tags):
        """
        Check whether or not a test should execute based on its tags

        Keyword arguments:
        requested_tags -- The list of tags used for selecting a subset of
            tests.  The test must have all tags to run.
        returns can_run - True if the test can execute, False otherwise
        """

        if not self.config:
            return False

        """ If no tags are requested, this test's tags don't matter """
        if not requested_tags:
            return self.can_run

        for tag in requested_tags:
            if tag.startswith("-"):
                try:
                    self.tags.index(tag[1:])
                    self.can_run = False
                    return self.can_run
                except:
                    pass
            else:
                try:
                    self.tags.index(tag)
                except:
                    self.can_run = False
                    return self.can_run

        # all tags matched successfully
        return self.can_run
