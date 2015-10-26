#!/usr/bin/env python
'''Simple email via SMTP

Copyright (C) 2015, Digium, Inc.
Jonathan Rose <jrose@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
'''


def send_email(server, sender, recipients, message, debug=0):
    """Send an email using SMTP

    server - host address of SMTP server
    sender - email address to use as the sender
    recipients - array of email addresses to send the message to
    message - dictionary containing a body and a subject for the message
    debug - optional argument sets debug level for smtp interface

    Note: This function uses print and is intended to be used outside the
    context of reactor.
    """

    print "Derp derp"

    try:
        import smtplib
    except ImportError:
        print "Failed to import smtplib"
        return -1

    print "Derpsti"

    if message['subject']:
        email_text = "Subject: {0}\n\n{1}".format(message['subject'],
                                                  message['body'])
    else:
        email_text = message['body']

    print "Shooping this whoop"

    try:
        smtp_obj = smtplib.SMTP(server)
        smtp_obj.set_debuglevel(debug)
        smtp_obj.sendmail(sender, recipients, email_text)
    except smtplib.SMTPServerDisconnected:
        print "Failed to connect to SMTP Server"
        return -1
    except smtplib.SMTPException as smtp_exception:
        print "Failed to send crash report due to unhandled SMTPException"
        raise(smtp_exception)

    return 0
