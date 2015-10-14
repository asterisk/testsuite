#!/usr/bin/env python
'''
Copyright (C) 2015, Digium, Inc.
Ashley Sanders <asanders@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
'''

import yaml
import sys
import os
import errno
import subprocess
import optparse
import time
import yaml
import shutil
import xml.dom
import random
import select
import traceback

from collections import OrderedDict

TESTS_CONFIG = "tests.yaml"

def ordered_load(stream, Loader=yaml.Loader, object_pairs_hook=OrderedDict):
    class OrderedLoader(Loader):
        pass
    def construct_mapping(loader, node):
        loader.flatten_mapping(node)
        return object_pairs_hook(loader.construct_pairs(node))
    OrderedLoader.add_constructor(
        yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
        construct_mapping)
    return yaml.load(stream, OrderedLoader)

def ordered_dump(data, stream=None, Dumper=yaml.Dumper, **kwds):
    class OrderedDumper(Dumper):
        pass
    def _dict_representer(dumper, data):
        return dumper.represent_mapping(
            yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
            data.items())
    OrderedDumper.add_representer(OrderedDict, _dict_representer)
    return yaml.dump(data, stream, OrderedDumper, **kwds)


class TestFixer(object):
    def __init__(self, test_dir):
        self.tests = self._parse_test_yaml(test_dir)

    def _parse_test_yaml(self, test_dir):
        tests = []
        try:
            f = open("%s/%s" % (test_dir, TESTS_CONFIG), "r")
        except IOError:
            print "Failed to open %s/%s" % (test_dir, TESTS_CONFIG)
            return tests
        except:
            print "Unexpected error: %s" % sys.exc_info()[0]
            return tests

        config = yaml.load(f)
        f.close()

        for t in config["tests"]:
            for val in t:
                path = "%s/%s" % (test_dir, t[val])
                if val == "test":
                    tests.append(path)
                elif val == "dir":
                    tests += self._parse_test_yaml(path)

        return tests

    def run(self):

        for t in self.tests:
            print "--> Fixing test-config.yaml for test '%s' ..." % t
            my_test_config = "%s/test-config.yaml" % t
            my_config = self.get_config(my_test_config)

            if not my_config:
                print "ERROR: Failed to load configuration for test '%s'" % t
                return

            if not 'test-modules' in my_config:
                print "No test-modules block in configuration. Nothing to fix."
                continue
            if 'modules' not in my_config['test-modules']:
                print "No modules block in test-modules block. Nothing to fix."
                continue

            for module in my_config['test-modules']['modules']:
                if ('config-section' in module
                    and module['config-section'] in my_config):
                    if module['typename'] == 'rls_test.RLSTest':
                        valid = self.check_section(t, my_test_config, my_config, module["config-section"])
                        if not valid:
                            return False

        return True

    def check_section(self, test_name, my_test_config, my_config, config_section):

        clean_test_config = my_test_config.replace("external", "clean")
        clean_config = self.get_config(clean_test_config)

        my_module_config = my_config[config_section]
        clean_module_config = clean_config[config_section]

        my_packets = my_module_config["packets"]
        clean_resources = clean_module_config["resources"]
        clean_full_states = clean_module_config["full_state"]

        if clean_full_states is None:
            if clean_resources is None:
                print "DANGER WILL ROBINSON! %s is broken." % test_name
                return False
        elif clean_resources is None:
                print "DANGER WILL ROBINSON! %s is broken." % test_name
                return False

        if my_packets is None:
            print "DANGER WILL ROBINSON! %s is broken." % test_name
            return False

        for (x, packet) in enumerate(my_packets):
            if len(clean_full_states) <= x:
                print "DANGER WILL ROBINSON! %s FULLSTATE lengths are different." % test_name
                return False

            if clean_full_states[x] != packet["full_state"]:
                print "DANGER WILL ROBINSON! %s FULLSTATE '%s' values are different." % (test_name, x)
                return False

            if len(clean_resources) <= x:
                print "DANGER WILL ROBINSON! %s RESOURCES/PACKETS lengths are different." % test_name
                return False

            if cmp(clean_resources[x], packet["resources"]) != 0:
                print "DANGER WILL ROBINSON! %s RESOURCE[%s] values are different." % (test_name, x)
                return False

        return True

    def get_config(self, config_path):
        config = None
        with open(config_path, "r") as config_file:
            config = ordered_load(config_file, yaml.SafeLoader)
        return config

def main(argv=None):
    test_fixer = TestFixer(os.path.dirname(os.path.realpath(__file__)))
    #print "Fixing test-config.yaml files..."
    if not test_fixer.run():
        print "Something is very, very wrong. Check the printed statements."
    print "All clear."

if __name__ == "__main__":
    sys.exit(main() or 0)
