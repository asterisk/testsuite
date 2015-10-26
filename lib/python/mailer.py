#!/usr/bin/env python
"""Simple email via SMTP

Copyright (C) 2015, Digium, Inc.
Jonathan Rose <jrose@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
"""

try:
    import smtplib
    SMTP_AVAILABLE = True
except ImportError:
    SMTP_AVAILABLE = False


def send_email(server, sender, recipients, message, debug=0):
    """Send an email using SMTP

    Keyword Arguments:
    server - host address of SMTP server
    sender - email address to use as the sender
    recipients - array of email addresses to send the message to
    message - dictionary containing a body and a subject for the message
    debug - optional argument sets debug level for smtp interface

    Note: This function uses print and is intended to be used outside the
    context of reactor.
    """
    if not SMTP_AVAILABLE:
        print "smtplib could not be loaded, email functionality is unavailable"
        return -1

    subject = message.get('subject')
    if subject:
        email_text = "Subject: {0}\n\n{1}".format(subject,
                                                  message['body'])
    else:
        email_text = message['body']

    try:
        smtp_obj = smtplib.SMTP(server)
        smtp_obj.set_debuglevel(debug)
        smtp_obj.sendmail(sender, recipients, email_text)
    except smtplib.SMTPServerDisconnected:
        print "Failed to connect to SMTP Server"
        return -1
    except smtplib.SMTPException as smtp_exception:
        print "SMTP Error: {0}".format(smtp_exception)
        return -1

    return 0
