#!/usr/bin/env python
"""Pluggable module for tests that verify NOTIFY bodies.

Copyright (C) 2015, Digium, Inc.
John Bigelow <jbigelow@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
"""

import sys
import logging
import xml.etree.ElementTree as ET
import re

sys.path.append('lib/python')

from asterisk.pcap import VOIPListener

LOGGER = logging.getLogger(__name__)


class BodyCheck(VOIPListener):
    """SIP notify listener and expected results generator.

    A test module that observes incoming SIP notifies and generates the
    expected results for the body of each.
    """
    def __init__(self, module_config, test_object):
        """Constructor

        Arguments:
        module_config Dictionary containing test configuration
        test_object The test object for the running test.
        """
        self.set_pcap_defaults(module_config)
        VOIPListener.__init__(self, module_config, test_object)

        self.test_object = test_object
        self.token = test_object.create_fail_token("Haven't handled all "
                                                   "expected NOTIFY packets.")
        self.expected_config = module_config['expected_body']
        self.expected_notifies = int(module_config['expected_notifies'])
        self.body_type = module_config['expected_body_type']
        self.notify_count = 0

        if self.body_type.upper() not in ('PIDF', 'XPIDF'):
            msg = "Body type of '{0}' not supported."
            raise Exception(msg.format(self.body_type))

        if self.expected_config.get('namespaces') is not None:
            if self.expected_config['namespaces'].get('default') is None:
                msg = "Namespaces configuration does not include a 'default'."
                raise Exception(msg)

        # Add calback for SIP packets
        self.add_callback('SIP', self.packet_handler)

    def gen_expected_data(self):
        """Generate expected data results.

        Generates a single dictionary containing the expected results for a
        body.

        Returns:
        Dictionary of expected results.
        """
        expected_data = {}
        # Use full tags if we have namespaces.
        if self.expected_config.get('namespaces') is not None:
            full_tags = self.gen_full_tags()
        else:
            full_tags = self.expected_config['tags']

        # Get expected attributes corresponding to the notify body received.
        attribs = self.expected_config['attributes'][self.notify_count - 1]

        text = self.expected_config.get('text')
        # Get expected text corresponding to the notify body received.
        if text is not None:
            text = text[self.notify_count - 1]

        # Build dict of the expected results
        for full_tag in full_tags:
            expected_data[full_tag] = {}
            for tag in attribs.keys():
                if tag not in full_tag:
                    continue
                expected_data[full_tag]['attribs'] = attribs[tag]
            try:
                for tag in text.keys():
                    if tag not in full_tag:
                        continue
                    expected_data[full_tag]['text'] = text[tag]
            except AttributeError:
                pass

        return expected_data

    def gen_full_tags(self):
        """Generate fully qualified element tags.

        This generates fully qualified element tags by prefixing the tag name
        with it's corresponding namespace that is enclosed in curly braces.
        This is so our expected tags will properly match ElementTree tags.

        The format for an Element tag is: {<namespace>}<tag name>

        Returns:
        List of full tag names.
        """
        full_tags = []
        namespaces = self.expected_config['namespaces']

        for tag in self.expected_config['tags']:
            try:
                prefix, tag = tag.split(':')
                namespace = '{' + namespaces[prefix] + '}'
            except ValueError:
                namespace = '{' + namespaces['default'] + '}'
            except KeyError as keyerr:
                msg = "Key {0} not found in namespace configuration for tag."
                raise Exception(msg.format(keyerr))

            full_tags.append("{0}{1}".format(namespace, tag))

        return full_tags

    def set_pcap_defaults(self, module_config):
        """Set default PcapListener config that isn't explicitly overridden.

        Arguments:
        module_config Dict of module configuration
        """
        pcap_defaults = {'device': 'lo', 'snaplen': 2000,
                         'bpf-filter': 'udp port 5061', 'debug-packets': False,
                         'buffer-size': 4194304, 'register-observer': True}
        for name, value in pcap_defaults.items():
            module_config[name] = module_config.get(name, value)

    def packet_handler(self, packet):
        """Handle incoming SIP packets and verify contents.

        Check to see if a packet is a NOTIFY packet with the expected body
        type. If so then verify the body in the packet against the expected
        results.

        Arguments:
        packet Incoming SIP Packet
        """

        LOGGER.debug('Received SIP packet')

        if 'NOTIFY' not in packet.request_line:
            LOGGER.debug('Ignoring packet, not a NOTIFY.')
            return

        if packet.body.packet_type != self.body_type.upper():
            msg = "Ignoring packet, NOTIFY does not contain a '{0}' body type."
            LOGGER.warn(msg.format(self.body_type.upper()))
            return

        self.notify_count += 1

        # Generate dict of expected results for this notify body and validate
        # the body using it.
        expected = self.gen_expected_data()
        validator = Validator(self.test_object, packet, expected)
        if not validator.verify_body():
            LOGGER.error('Body validation failed.')
            return

        info_msg = "Body #{0} validated successfully."
        LOGGER.info(info_msg.format(self.notify_count))

        if self.notify_count == self.expected_notifies:
            self.test_object.remove_fail_token(self.token)
            self.test_object.set_passed(True)
            self.test_object.stop_reactor()


class Validator(object):
    """Validate a PIDF/XPIDF body against a set of expected data."""
    def __init__(self, test_object, packet, expected_data):
        """Constructor

        Arguments:
        test_object The test object for the running test.
        packet A packet containing a SIP NOTIFY with a pidf or xpidf body.
        """
        super(Validator, self).__init__()
        self.test_object = test_object
        self.packet = packet
        self.body_types = ('PIDF', 'XPIDF')
        self.expected_data = expected_data

    def verify_body(self):
        """Verify a PIDF/XPIDF body.

        This uses XML ElementTree to parse the PIDF/XPIDF body. It verifies
        that the XML is not malformed and verifies the elements match what is
        expected. This will fail the test and stop the reactor if the body type
        is not recognized or if the body could not be parsed.

        Returns:
        True if body type is supported, body is successfully parsed, and body
        matches what is expected. False otherwise.
        """
        if self.packet.body.packet_type not in self.body_types:
            msg = "Unrecognized body type of '{0}'"
            self.fail_test(msg.format(self.packet.body.packet_type))
            return False

        # Attempt to parse the body
        try:
            root = ET.fromstring(self.packet.body.xml)
        except Exception as ex:
            self.fail_test("Exception when parsing body XML: %s" % ex)
            return False

        # Verify top-level elements and their children
        for element in root.findall('.'):
            if not self.verify_element(element):
                return False

        return True

    def verify_element(self, element):
        """Verify the element matches what is expected.

        This verifies the tag, attributes, text, and extra text of an element.
        If child elements are found this will call back into itself to verify
        them.

        Arguments:
        element Element object.

        Returns:
        True if the element matches what is expected. False otherwise.
        """
        # Verify tag, attributes, text, and extra text of the element.
        if not self.verify_tag(element):
            return False
        if not self.verify_attributes(element):
            return False
        if not self.verify_text(element):
            return False
        if not self.verify_extra_text(element):
            return False

        # Find child elements
        children = element.findall('*')
        if not children:
            return True

        # Verify child elements.
        for child in children:
            if not self.verify_element(child):
                return False

        return True

    def verify_tag(self, element):
        """Verify element tag is expected.

        This will fail the test and stop the reactor if the element tag is not
        expected.

        Arguments:
        element Element object.

        Returns:
        True if element tag is in expected tags. False otherwise.
        """
        LOGGER.debug("Checking tag: '{0}'".format(element.tag))
        if element.tag in self.expected_data.keys():
            return True

        self.fail_test("Unexpected tag: '{0}'.".format(element.tag))

        return False

    def verify_attributes(self, element):
        """Verify element attributes.

        Ensure the element contains only the attributes that are expected and
        the attribute values match what are expected. This will fail the test
        and stop the reactor if conditions are not met.

        Arguments:
        element Element object.

        Returns:
        True if attributes not expected and none found, expected attribute
        values match found attribute values. Otherwise False.
        """
        expected = self.expected_data[element.tag].get('attribs')
        LOGGER.debug("Checking attributes.")

        # If attributes are not expected and none are in the element then
        # there's nothing more to do.
        if not element.keys() and expected is None:
            msg = "Attributes not expected and none found."
            LOGGER.debug(msg.format())
            return True

        # Check if we expect attributes but element doesn't have any.
        if not element.keys() and expected is not None:
            msg = "Expected attributes not found: {0}"
            self.fail_test(msg.format(', '.join(expected.keys())))
            return False

        # Check if we don't expect attributes but element has some.
        if element.keys() and expected is None:
            msg = "Unexpected attributes found: {0}"
            self.fail_test(msg.format(', '.join(element.keys())))
            return False

        # Ensure all expected attributes exist in the element.
        not_found = [ex for ex in expected.keys() if ex not in element.keys()]
        if not_found:
            msg = "Expected attributes not found in element: {0}"
            self.fail_test(msg.format(', '.join(not_found)))
            return False

        for xml_attrib in element.keys():
            LOGGER.debug("Checking attribute: '{0}'".format(xml_attrib))
            # Check if we don't expect attributes this particular attribute for
            # this element.
            if expected.get(xml_attrib) is None:
                msg = "Unexpected attribute found: '{0}'"
                self.fail_test(msg.format(xml_attrib))
                return False

            if not re.match(expected[xml_attrib], element.get(xml_attrib)):
                msg = "Attribute '{0}' value '{1}' does not match '{2}'"
                self.fail_test(msg.format(xml_attrib, element.get(xml_attrib),
                                          expected[xml_attrib]))
                return False

        return True

    def verify_text(self, element):
        """Verify element text.

        Ensure the element text matches the expected text. This will fail the
        test and stop the reactor if conditions are not met.

        Arguments:
        element Element object.

        Returns:
        True if element text matches expected text. Otherwise False.
        """
        expected = self.expected_data[element.tag].get('text', '')
        element_text = element.text

        # Set to empty string if None so we can strip it and try to match it.
        if element_text is None:
            element_text = ''
        element_text = element_text.strip()

        LOGGER.debug("Checking text: '{0}'".format(element_text))
        # Check if we don't expect any text or we don't expect this particular
        # text for this element.
        if element_text and not expected:
            msg = "Unexpected text found: '{0}'"
            self.fail_test(msg.format(element_text))
            return False

        # Check if we expect text but element doesn't have any.
        if not element_text and expected:
            msg = "Expected text not found: '{0}'"
            self.fail_test(msg.format(expected))
            return False

        if not re.match(expected, element_text):
            msg = "Element text '{0}' does not match '{1}'"
            self.fail_test(msg.format(element_text, expected))
            return False

        return True

    def verify_extra_text(self, element):
        """Verify extra text is not present in element.

        Ensure there is no extra text in the element. This will fail the test
        and stop the reactor if extra text is found.

        Arguments:
        element Element object.

        Returns:
        True if extra text was not found or only whitespace was found.
        Otherwise False.
        """
        LOGGER.debug("Checking for extra text.")
        if element.tail is None:
            return True

        # Ignore any whitespace
        extra_text = str(element.tail)
        extra_text = extra_text.strip()
        if not extra_text:
            return True

        msg = "Unexpected extra text found on element '%s': '%s'"
        self.fail_test(msg.format(element.tag, extra_text))

        return False

    def fail_test(self, message):
        """Mark the test as failed and stop the reactor

        Arguments:
        message Reason for the test failure
        """
        LOGGER.error(message)
        self.test_object.set_passed(False)
        self.test_object.stop_reactor()
