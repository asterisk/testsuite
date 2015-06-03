#!/usr/bin/env python
"""Find a symbol from the address of an unloaded module.

 This script uses a process map to determine which module
 an unloaded address was from, uses the information to run
 addr2line.

 See http://www.asterisk.org for more information about
 the Asterisk project. Please do not directly contact
 any of the maintainers of this project for assistance;
 the project provides a web site, mailing lists and IRC
 channels for your use.

 This program is free software, distributed under the terms of
 the GNU General Public License Version 2. See the LICENSE file
 at the top of the source tree.

 Copyright (C) 2015, CFWare, LLC
 Corey Farrell <git@cfware.com>
"""

import sys
import os

from optparse import OptionParser


def main(argv=None):
    """Main entry point for the script"""

    if argv is None:
        argv = sys.argv

    parser = OptionParser()
    parser.add_option("-m", "--process-map", action="store", type="string",
                      dest="mappath", default=None,
                      help="The full path to the copy of /proc/self/maps.")
    parser.add_option("-a", "--address", action="store", type="string",
                      dest="address", default=None,
                      help="A pointer from an unloaded module.")

    (options, args) = parser.parse_args(argv)
    if not options.mappath or not options.address:
        print >>sys.stderr, "Both options are required."
        return -1

    if not os.path.isfile(options.mappath):
        print >>sys.stderr, "File not found: %s" % options.mappath
        return -1

    find_addr = int(options.address, 16)
    with open(options.mappath, 'r') as mapfile:
        for line in mapfile:
            tokens = line.strip().replace('  ', ' ').split()
            addr = tokens[0].split('-')
            addr[0] = int(addr[0], 16)
            addr[1] = int(addr[1], 16)

            # TODO: verify that '>= and <' is the correct range
            if find_addr >= addr[0] and find_addr < addr[1]:
                offset = find_addr - addr[0]
                if len(tokens) < 6 or tokens[5].startswith('['):
                    print "This address is not associated with a module"
                    return 0
                module = tokens[5]
                print "Found symbol at offset 0x%x of %s" % (offset, module)
                os.execl('/usr/bin/addr2line',
                         'addr2line', '-spfe', module, "0x%x" % offset)

                # This location should be unreachable..
                return -1

    print >>sys.stderr, \
        "No range contained the address %s, verify you have the correct process map." % \
        options.address

    return -1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
