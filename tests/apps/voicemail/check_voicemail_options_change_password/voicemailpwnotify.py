#!/usr/bin/env python
''' externpassnotify script for use with check_voicemail_options_change_password test

Copyright (C) 2011, Digium, Inc.
Matt Jordan <mjordan@digium.com>

This script acts as a receiver for voicemail password change notifications.  It accepts
the voicemail password change, and returns 0 if the change has the values it expects; otherwise
it returns 1
'''

import sys

def main(argv = sys.argv):

    context, mailbox, new_pw = argv[1:4]

    if context == "default" and mailbox == "1234" and new_pw == "555666":
        return 0
    else:
        return 1

if __name__ == "__main__":
   sys.exit(main() or 0)