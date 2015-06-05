#/usr/bin/env python
"""
Copyright (C) 2015, Digium, Inc.
Jonathan Rose <jrose@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
"""

import logging
import xml.etree.ElementTree as ET

LOGGER = logging.getLogger(__name__)


def count_parts(parts, packet_type):
    """Count the number of parts of a particular type in a multipart body"""
    return sum([1 for x in parts if x.body.packet_type == packet_type])


class RLSValidator(object):
    """General class that validates a multipart RLS NOTIFY body"""
    def __init__(self, test_object, packet, version, full_state, list_name,
                 resources):
        """Constructor

        Arguments:
        test_object The test object for the running test.
        packet The Multipart NOTIFY body in full.
        version The expected RLMI version attribute. Expressed as an integer.
        full_state The expected RLMI fullState attribute. Expressed as a
                   boolean.
        list_name The expected RLMI name element value.
        packet_type The type of body parts to expect other than RLMI.
        resources A dictionary of the resource names and their expected state.
        """
        super(RLSValidator, self).__init__()
        self.test_object = test_object
        self.packet = packet
        self.version = version
        self.full_state = full_state
        self.list_name = list_name
        self.resources = resources
        self.rlmi_cids = {}
        self.resource_cids = {}

    def validate_body_part(self, part, resources, rlmi, list_name):
        """Validates a single body part against the its packet type validator

        Note: Will mark the test as failed if the packet does not match
        expectations

        Returns:
        True if the component matched expectations
        False if the component did not match expectations
        """
        if part.body.packet_type == 'RLMI':
            return self.validate_rlmi(part.body.list_elem, resources,
                                      list_name)
        elif part.body.packet_type == 'PIDF':
            return self.validate_pidf(part.body, resources)
        elif part.body.packet_type == 'MWI':
            return self.validate_mwi(part.body, resources, rlmi)
        elif part.body.packet_type == 'Multipart':
            return self.validate_multipart(part, resources)

        msg = "Unrecognized body part packet type of '{0}'"
        self.fail_test(msg.format(part.body.packet_type))
        return False

    def check_integrity(self):
        """Validates a multipart RLS body

        If the multipart body does not pass validation, then the test will
        fail. If this method returns at all, it means that the body passed
        validation.

        Returns:
        True if the multipart RLS body matches the expectations provided at
             construction
        False if the multipart RLS body does not match the expectations
        """
        rlmi = None

        # Number of resources plus an RLMI part
        if len(self.packet.body.parts) != len(self.resources) + 1:
            self.fail_test("Unexpected number of parts (%d) in multipart body"
                           % len(self.packet.body.parts))
            return False

        rlmi_parts = count_parts(self.packet.body.parts, 'RLMI')
        resource_parts = len(self.packet.body.parts) - 1

        if rlmi_parts != 1:
            self.fail_test("Unexpected number of RLMI parts (%d) in multipart"
                           "body" % rlmi_parts)
            return False

        if resource_parts != len(self.resources):
            self.fail_test("Unexpected number of parts (%d) in multipart"
                           "body" % resource_parts)
            return False

        for part in self.packet.body.parts:
            if part.body.packet_type == 'RLMI':
                rlmi = part
                break

        for part in self.packet.body.parts:
            x = self.validate_body_part(part, self.resources, rlmi,
                                        self.list_name)
            if not x:
                return False

        if len(self.rlmi_cids) != len(self.resource_cids):
            self.fail_test("Gathered mismatching number of Content IDs. RLMI"
                           "document has %d. Should have %d" %
                           (len(self.rlmi_cids), len(self.resource_cids)))
            return False

        for uri, cid in self.rlmi_cids.iteritems():
            if uri not in self.resource_cids:
                self.fail_test("URI not found in %s documents" %
                               (uri))
                return False
            if self.resource_cids.get(uri) != cid:
                self.fail_test("Mismatching Content ID for URI %s. RLMI"
                               "document has %s. Document has %s" %
                               (uri, cid, self.resource_cids.get(uri)))
                return False

        return True

    def validate_rlmi(self, list_elem, resources, list_name):
        """Validate an RLMI document

        This method checks the integrity of the list element and calls
        into a helper method to check the integrity of each resource
        element in the list.

        Arguments:
        list_elem The XML <list> element in the RLMI body, as parsed by pyxb
        resources The expected resources dictionary relevant to this RLMI body
        """

        if list_elem.version != self.version:
            self.fail_test("Unexpected RLMI version %d" % list_elem.version)
            return False

        if list_elem.fullState != self.full_state:
            self.fail_test("Unexpected fullState value %s" %
                           str(list_elem.fullState))
            return False

        if len(list_elem.name) != 1:
            self.fail_test("Unexpected number of names (%d) in RLMI list" %
                           len(list_elem.name))
            return False

        if len(list_elem.resource) != len(resources):
            self.fail_test("Unexpected number of resources (%d) in RLMI list" %
                           len(list_elem.resource))
            return False

        if list_elem.name[0].value() != list_name:
            self.fail_test("Unexpected list name: %s" %
                           list_elem.name[0].value())
            return False

        for resource in list_elem.resource:
            if not self.validate_rlmi_resource(resource, resources):
                return False
        return True

    def validate_rlmi_resource(self, rlmi_resource, resources):
        """Validate an RLMI resource

        This method checks the integrity of a resource XML element within an
        RLMI list.

        Arguments:
        rlmi_resource The XML <resource> element in the RLMI <list>, as parsed
        by pyxb
        resources The expected resources dictionary relevant to this RLMI
            resource
        """
        if not rlmi_resource.uri:
            self.fail_test("Resource is missing a URI")
            return False

        if len(rlmi_resource.name) != 1:
            self.fail_test("Unexpected number of names (%d) in resource" %
                           len(rlmi_resource.name))
            return False

        if len(rlmi_resource.instance) != 1:
            self.fail_test("Unexpeced number of instances (%d) in resource" %
                           len(rlmi_resource.instance))
            return False

        name = rlmi_resource.name[0].value()
        if name not in resources:
            self.fail_test("Unexpected resource name %s" % name)
            return False

        instance = rlmi_resource.instance[0]
        if not instance.state:
            self.fail_test("Resource instance has no state")
            return False
        if not instance.id:
            self.fail_test("Resource instance has no id")
            return False
        if not instance.cid:
            self.fail_test("Resource instance has no cid")
            return False

        if instance.state != resources[name]['state']:
            self.fail_test("Unexpected instance state %s" % instance.state)
            return False

        self.rlmi_cids[rlmi_resource.uri] = rlmi_resource.instance[0].cid
        return True

    def validate_pidf(self, pidf_part, resources):
        """Validates the integrity of a PIDF body

        This uses XML ElementTree to parse the PIDF body and ensures basic
        structural elements (as they relate to RLS) are present.

        Arguments:
        pidf_part The PIDF part from a multipart body.
        resources The expected resources dictionary relevant to this PIDF body

        Returns:
        True if the pidf_part matched the expectations in resources
        False if the pidf_part did not match the expectations in resources
        """

        if not pidf_part.content_id:
            self.fail_test("PIDF part does not have a Content-ID")
            return False

        try:
            root = ET.fromstring(pidf_part.xml)
        except Exception as ex:
            self.fail_test("Exception when parsing PIDF XML: %s" % ex)
            return False

        entity = root.get('entity')
        if not entity:
            self.fail_test("PIDF document root has no entity")
            return False

        stripped_entity = entity.strip('<>')
        self.resource_cids[stripped_entity] = pidf_part.content_id
        return True

    def validate_mwi(self, mwi_part, resources, rlmi):
        """Validates the integrity of an MWI body

        this uses the rlmi that included the mwi body so that its
        name and URI can be determined and linked to the appropriate
        resource.

        Arguments:
        mwi_part The MWI part from a multipart body
        resources The expected resources dictionary relevant to this MWI body
        rlmi The rlmi that described the WMI body

        Returns:
        True if the mwi_part matched the expectations in resources
        False if the mwi_part did not match the expectations in resources
        """
        if not mwi_part.content_id:
            self.fail_test("MWI part does not have a Content-ID")
            return False

        if not rlmi:
            self.fail_test("MWI part has now RLMI body")
            return False

        my_name = None
        my_uri = None

        # Yeargh, who the heck am I anyway?
        for resource in rlmi.body.list_elem.resource:
            if resource.instance[0].cid == mwi_part.content_id:
                my_name = resource.name[0].value()
                my_uri = resource.uri
                break

        if not my_name:
            self.fail_test("Couldn't find MWI part with Content ID '%s' in "
                           "MWI body" % mwi_part.content_id)
            return False

        if not my_uri:
            self.fail_test("URI not found for resource '%s'" % my_name)
            return False

        relevant_resource = resources.get(my_name)
        if not relevant_resource:
            self.fail_test("MWI '%s' not specified in expected resources" %
                           my_name)
            return False

        if relevant_resource['type'] != 'MWI':
            self.fail_test("Resource expected type isn't an MWI type.")
            return False

        if relevant_resource['voice_message'] != mwi_part.voice_message:
            self.fail_test("Voice-Message header doesn't match expectations")
            return False

        if relevant_resource['messages_waiting'] != mwi_part.messages_waiting:
            self.fail_test("Messages-Waiting header doesn't match " +
                           "expectations")
            return False

        self.resource_cids[my_uri] = mwi_part.content_id
        return True

    def validate_multipart(self, multi_part, resources):
        """Validates the integrity of a Multipart body

        This filters down through parts within the multipart body
        in order to recursively evaluate each element contained
        within.

        Arguments:
        multi_part The Multipart part from a multipart body.
        resources The expected resources dictionary relevant for this
            multipart body. May be the full list specified by the test
            or a deeper node.

        Returns:
        True if the multi_part body matches the expectations in resources
        False if the multi_part body does not match the expectations
        """
        rlmi = None

        if not multi_part.content_id:
            self.fail_test("Multipart does not have a Content-ID")
            return False

        for part in multi_part.body.parts:
            if part.body.packet_type == 'RLMI':
                rlmi = part
                name = part.body.list_elem.name[0].value()
                uri = part.body.list_elem.uri

        self.resource_cids[uri] = multi_part.content_id

        next_resources = resources.get(name)
        if not next_resources:
            self.fail_test("Missing '%s'" % name)
            return False

        if next_resources['type'] != 'Multipart':
            self.fail_test("Packet Type is wrong -- processing multipart, "
                           "but expected type is %s" % next_resources['type'])
            return False

        next_resources = next_resources['sublist']

        for part in multi_part.body.parts:
            if not self.validate_body_part(part, next_resources, rlmi, name):
                return False
        return True

    def fail_test(self, message):
        """Mark the test as failed and stop the reactor

        Arguments:
        message Reason for the test failure"""
        LOGGER.error(message)
        self.test_object.set_passed(False)
        self.test_object.stop_reactor()

