#!/usr/bin/env python
"""Module that spawns and manages running a test

This module provides an entry point, loading, and teardown of test
runs for the Test Suite

Copyright (C) 2014, Digium, Inc.
Matt Jordan <mjordan@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
"""

import sys
import imp
import logging
import logging.config
import os
import yaml

from twisted.internet import reactor

LOGGER = logging.getLogger('test_runner')
logging.basicConfig()

sys.path.append('lib/python')


class TestModuleFinder(object):
    """Determines if a module is a test module that can be loaded"""

    supported_paths = []

    def __init__(self, path_entry):
        """Constructor

        path_entry The path to look for test modules in
        """
        if not path_entry in TestModuleFinder.supported_paths:
            raise ImportError()
        LOGGER.debug("TestModuleFinder supports path %s" % path_entry)
        return

    def find_module(self, fullname, suggested_path=None):
        """Attempts to find the specified module

        Keyword Arguments:
        fullname       The full name of the module to load
        suggested_path Optional path to find the module at
        """
        search_paths = TestModuleFinder.supported_paths
        if suggested_path:
            search_paths.append(suggested_path)
        for path in search_paths:
            if os.path.exists('%s/%s.py' % (path, fullname)):
                return TestModuleLoader(path)
        LOGGER.debug("Unable to find module '%s'" % fullname)
        return None


class TestModuleLoader(object):
    """Loads modules defined in the tests"""

    def __init__(self, path_entry):
        """Constructor

        Keyword Arguments:
        path_entry The path the module is located at
        """
        self._path_entry = path_entry

    def _get_filename(self, fullname):
        """Get the full path to the specified python file"""
        return '%s/%s.py' % (self._path_entry, fullname)

    def load_module(self, fullname):
        """Load the module into memory

        Keyword Arguments:
        fullname The full name of the module to load
        """
        if fullname in sys.modules:
            mod = sys.modules[fullname]
        else:
            mod = sys.modules.setdefault(
                fullname,
                imp.load_source(fullname, self._get_filename(fullname)))

        return mod


sys.path_hooks.append(TestModuleFinder)


def load_test_modules(test_config, test_object):
    """Load the pluggable modules for a test

    Keyword Arguments:
    test_config The test configuration object
    test_object The test object that the modules will attach to
    """

    if not test_object:
        return
    if not 'test-modules' in test_config:
        LOGGER.error("No test-modules block in configuration")
        return
    if 'modules' not in test_config['test-modules']:
        # Not an error - just no pluggable modules specified
        return

    for module_spec in test_config['test-modules']['modules']:
        # If there's a specific portion of the config for this module,
        # use it
        if ('config-section' in module_spec
                and module_spec['config-section'] in test_config):
            module_config = test_config[module_spec['config-section']]
        else:
            module_config = test_config

        module_type = load_and_parse_module(module_spec['typename'])
        # Modules take in two parameters: the module configuration object,
        # and the test object that they attach to
        module_type(module_config, test_object)


def load_and_parse_module(type_name):
    """Take a qualified module/object name, load the module, and return
    a typename specifying the object

    Keyword Arguments:
    type_name A fully qualified module/object to load into memory

    Returns:
    An object type that to be instantiated
    None on error
    """

    LOGGER.debug("Importing %s" % type_name)

    # Split the object typename into its constituent parts - the module name
    # and the actual type of the object in that module
    parts = type_name.split('.')
    module_name = ".".join(parts[:-1])

    if not len(module_name):
        LOGGER.error("No module specified: %s" % module_name)
        return None

    module = __import__(module_name)
    for comp in parts[1:]:
        module = getattr(module, comp)
    return module


def create_test_object(test_path, test_config):
    """Create the specified test object from the test configuration

    Parameters:
    test_path   The path to the test directory
    test_config The test configuration object, read from the yaml file

    Returns:
    A test object that has at least the following:
        - __init__(test_path) - constructor that takes in the location of the
            test directory
        - evaluate_results() - True if the test passed, False otherwise
    Or None if the object couldn't be created.
    """
    def get_test_object():
        objs = test_config['test-modules']['test-object']
        if not isinstance(objs, list):
            objs = [objs]
        return next((obj for obj in objs), None)

    if not 'test-modules' in test_config:
        LOGGER.error("No test-modules block in configuration")
        return None
    if not 'test-object' in test_config['test-modules']:
        LOGGER.error("No test-object specified for this test")
        return None

    test_object_spec = get_test_object()
    if not test_object_spec:
        LOGGER.error("No test-object found for version range(s)")
        return None

    module_obj = load_and_parse_module(test_object_spec['typename'])
    if module_obj is None:
        return None

    test_object_config = None
    if ('config-section' in test_object_spec
            and test_object_spec['config-section'] in test_config):
        test_object_config = test_config[test_object_spec['config-section']]
    else:
        test_object_config = test_config

    # The test object must support injection of its location as a parameter
    # to the constructor, and its test-configuration object (or the full test
    # config object, if none is specified)
    test_obj = module_obj(test_path, test_object_config)
    return test_obj


def load_test_config(test_directory):
    """Load and parse the yaml test config specified by the test_directory

    Note: this will throw exceptions if an error occurs while parsing the yaml
    file. This is expected: if you provide an invalid configuration, it's far
    easier to let this crash and fix the yaml then try and 'handle' a completely
    invalid configuration gracefully.

    Parameters:
    test_directory The directory containing this test run's information

    Returns:
    An object containing the yaml configuration, or None on error
    """

    test_config = None

    # Load and parse the test configuration
    test_config_path = ('%s/test-config.yaml' % test_directory)
    if not os.path.exists(test_config_path):
        LOGGER.error("No test-config.yaml file found in %s" % test_directory)
        return test_config

    with open(test_config_path) as file_stream:
        test_config = yaml.load(file_stream, Loader=yaml.SafeLoader)

    return test_config


def read_module_paths(test_config, test_path):
    """Read additional paths required for loading modules for the test

    Parameters:
    test_config The test configuration object
    """

    if not 'test-modules' in test_config:
        # Don't log anything. The test will complain later when
        # attempting to load modules
        return

    if ('add-test-to-search-path' in test_config['test-modules'] and
            test_config['test-modules']['add-test-to-search-path']):
        TestModuleFinder.supported_paths.append(test_path)
        sys.path.append(test_path)

    if 'add-to-search-path' in test_config['test-modules']:
        for path in test_config['test-modules']['add-to-search-path']:
            TestModuleFinder.supported_paths.append(path)
            sys.path.append(path)

    if 'add-relative-to-search-path' in test_config['test-modules']:
        for path in test_config['test-modules']['add-relative-to-search-path']:
            TestModuleFinder.supported_paths.append(os.path.join(test_path, path))
            sys.path.append(os.path.join(test_path, path))


def main(argv=None):
    """Main entry point for the test run

    Returns:
    0 on successful test run
    1 on any error
    """

    if argv is None:
        args = sys.argv

    if (len(args) < 2):
        LOGGER.error("test_runner requires the full path to the test "
                     "directory to execute")
        return 1
    test_directory = args[1]

    LOGGER.info("Starting test run for %s" % test_directory)
    test_config = load_test_config(test_directory)
    if test_config is None:
        return 1

    read_module_paths(test_config, test_directory)

    test_object = create_test_object(test_directory, test_config)
    if test_object is None:
        return 1

    # Load other modules that may be specified
    load_test_modules(test_config, test_object)

    # Load global modules as well
    if test_object.global_config.config:
        load_test_modules(test_object.global_config.config, test_object)

    # Kick off the twisted reactor
    reactor.run()

    LOGGER.info("Test run for %s completed with result %s" %
                (test_directory, str(test_object.passed)))
    if test_object.evaluate_results():
        return 0

    return 1


if __name__ == '__main__':
    sys.exit(main() or 0)
