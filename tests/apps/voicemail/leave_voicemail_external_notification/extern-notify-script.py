#!/usr/bin/env python
# vim: sw=3 et:
'''
Copyright (C) 2011, Digium, Inc.
Matt Jordan <mjordan@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
'''

"""
This will be called with the following arguments, per app_voicemail:
    context extension newvoicemails oldvoicemails urgentvoicemails

"""

import sys

def main(argv = sys.argv):

    context = argv[1]
    extension = argv[2]
    newvoicemails = argv[3]
    oldvoicemails = argv[4]
    urgentvoicemails = argv[5]

    """
    Write out the passed in variables so the test can check them
    """

    f = open('/tmp/asterisk-testsuite/' + context + '_' + extension + '.txt', 'w')
    f.write('Context=' + context + '\n')
    f.write('Extension=' + extension + '\n')
    f.write('NewVoicemails=' + str(newvoicemails) + '\n')
    f.write('OldVoicemails=' + str(oldvoicemails) + '\n')
    f.write('UrgentVoicemails=' + str(urgentvoicemails) + '\n')

    f.close()

    return 1

if __name__ == "__main__":
   sys.exit(main() or 0)