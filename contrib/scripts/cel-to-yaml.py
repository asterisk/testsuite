#!/usr/bin/env python
"""Script that turns a CEL CSV file into a blob of YAML suitable
for parsing by the CELModule

Copyright (C) 2013, Digium, Inc.
Matt Jordan <mjordan@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
"""

import sys
import os
import optparse
import yaml

def main(argv=None):
    if argv is None:
        args = sys.argv

    parser = optparse.OptionParser()
    parser.add_option("-i", "--input",
            dest="input_file",
            help="Specify the input CEL file to process")
    parser.add_option("-c", "--column", action="append",
            dest="columns",
            help="Add a column to the output. Can be used multiple times.")
    (options, args) = parser.parse_args(argv)

    columns = ["eventtype", "cidname", "cidnum", "dnid", "exten", "context",
               "channel", "app"]
    if options.columns:
        for c in options.columns:
            columns.append(c)
    fields = ['eventtype', 'eventtime', 'cidname', 'cidnum', 'ani', 'rdnis',
    'dnid', 'exten', 'context', 'channel', 'app', 'appdata', 'amaflags',
    'accountcode', 'uniqueid', 'linkedid', 'bridgepeer', 'userfield',
    'userdeftype', 'eventextra']

    input_file = open(options.input_file)
    result = []
    for line in input_file.readlines():
        tokens = line.split(',')
        blob = {}
        for column in columns:
            index = fields.index(column)
            blob[column] = str(tokens[index].replace('"','').strip())
        result.append(blob)
    raw_yaml = yaml.dump(result)
    raw_yaml = raw_yaml.replace(',', '\n').replace('}', '').replace('{', '')
    print raw_yaml

    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)