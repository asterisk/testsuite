#!/usr/bin/env python
'''
Copyright (C) 2010, Digium, Inc.
Russell Bryant <russell@digium.com>
'''

import sys
import optparse
import yaml

TESTS_CONFIG = "tests/tests.yaml"

class TestsConfig:
    def __init__(self):
        f = open(TESTS_CONFIG, "r")
        self.config = yaml.load(f)
        f.close()

    def __str__(self):
        s = "Configured tests:\n"
        i = 1
        for t in self.config["tests"]:
            s += "%.3d) %s\n" % (i, t["test"])
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

    print "Executing the tests is not yet implemented.  Try --list-tests !"


if __name__ == "__main__":
    main()
