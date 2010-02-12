#!/usr/bin/env python
'''
Copyright (C) 2010, Digium, Inc.
Russell Bryant <russell@digium.com>
'''

import sys
import optparse
import yaml

TESTS_CONFIG = "tests/tests.yaml"

class TestConfig:
    def __init__(self, test_name):
        f = open("tests/%s/test-config.yaml" % test_name, "r")
        self.config = yaml.load(f)
        f.close()
        self.test_name = test_name

    def summary(self):
        return self.config["testinfo"]["summary"]


class TestsConfig:
    def __init__(self):
        f = open(TESTS_CONFIG, "r")
        self.config = yaml.load(f)
        f.close()

        self.tests = []
        for t in self.config["tests"]:
            self.tests.append(TestConfig(t["test"]))

    def __str__(self):
        s = "Configured tests:\n"
        i = 1
        for t in self.tests:
            s += "%.3d) %s (%s)\n" % (i, t.test_name, t.summary())
            i += 1
        return s


def main(argv=None):
    if argv is None:
        args = sys.argv

    parser = optparse.OptionParser()
    parser.add_option("-l", "--list-tests", action="store_true",
            dest="list_tests", default=False,
            help="List tests instead of running them.")
    (options, args) = parser.parse_args(argv)

    tests_config = TestsConfig()

    if options.list_tests is True:
        print tests_config
        sys.exit(0)

    print "Executing the tests is not yet implemented.  Try --list-tests"


if __name__ == "__main__":
    main()
