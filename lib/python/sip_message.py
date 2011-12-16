#!/usr/bin/env python
import re

class SIPParseError(Exception):
    pass

# This is not particularly efficient. I don't care.
# Ok, I do, but I'm not going to do anything about it.
class SIPMessage:
    """ This generally parses out the first line, headers, and body in a SIP message.
    It does not ensure that those parts are in any way valid"""
    def __init__(self, data):
        self.first_line = None
        self.body = None
        self.headers = None

        # First, split the msg into header and body
        try:
            (data, self.body) = data.split("\r\n\r\n", 1)
        except ValueError:
            # No message body
            pass

        try:
            # Now, seperate Request/Response line from the rest of the data
            (self.first_line, rest) = data.split("\r\n", 1)

            # Now convert any multi-line headers to a single line, and then split on newlines
            header_array = re.sub(r'\r\n[ \t]+', ' ', rest).split("\r\n")

            # Now convert the headers into an array of (field, val) tuples
            self.headers = []
            for h in header_array:
                (field, val) = h.split(':', 1)
                self.headers.append((field.rstrip(' \t').lower(), val.lstrip(' \t')))
        except:
            raise SIPParseError()

    def get_header(self, header):
        for h in self.headers:
            if h[0] == header.lower():
                return h[1]

    def get_header_all(self, header):
        res = []
        for h in self.headers:
            if h[0] == header.lower():
                res.append(h[1])
        return res

    def __str__(self):
        return "%s\r\n%s\r\n\r\n%s" % (self.first_line, "\r\n".join(["%s: %s" % (h[0].title(), h[1]) for h in self.headers]), self.body)


class SIPMessageTest(object):
    def __init__(self, pass_callback=None):
        self.passed = False
        self.matches_left = []
        self.matches_passed = []
        self.pass_callback = pass_callback

    def add_required_match(self, match):
        """Add a list of pattern matches that a single packet must match

        match is an array of two-tuples, position 0 is either:
            "first_line", "body", or a header name
        position 1 is a regular expression to match against that portion
        of the SIPMessage. For example, match any SIP INVITE that has a
        Call-ID, match could be:
            [("first_line", r'^INVITE', ('Call-ID', r'.*')]

        For a packet to pass a match, all elements of the match must pass.
        For the SIPMessageTest itself to pass, all added match arrays must
        pass.

        """
        self.matches_left.append(match)

    def _match_val(self, regex, arr):
        for val in arr:
            if re.search(regex, val) is not None:
                return True
        return False

    def _match_match(self, sipmsg, match):
        (key, regex) = match
        if key == "first_line":
            it = [sipmsg.first_line]
        elif key == "body":
            it = [sipmsg.body]
        else:
            it = sipmsg.get_header_all(key)

        return self._match_val(regex, it)


    def test_sip_msg(self, sipmsg):
        if len(self.matches_left) > 0:
            test = self.matches_left[0]
            for match in test:
                if self._match_match(sipmsg, match):
                    self.matches_passed.append(test)
                    del self.matches_left[0]
                    if len(self.matches_left) == 0:
                        self.passed = True
                        if self.pass_callback is not None:
                            self.pass_callback()
                    break


def main():
    msg = """INVITE sip:123@example.com SIP/2.0\r\nContact   : \tTerry Wilson\r\n   <terry@example.com>\r\nCall-ID:\r\n Whatever\r\nContact: New Contact\r\n\r\nData!!!!!"""
    sipmsg = SIPMessage(msg)
    print sipmsg
    if sipmsg.get_header('CoNtact') is None:
        return -1
    if len(sipmsg.get_header_all('contact')) != 2:
        return -1

if __name__ == '__main__':
    import sys
    sys.exit(main())
