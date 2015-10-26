#/usr/bin/env python
"""
Copyright (C) 2015, Digium, Inc.
Jonathan Rose <jrose@digium.com>
Ashley Sanders <asanders@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
"""

import sys
import logging
import xml.etree.ElementTree as ET

sys.path.append('lib/python')
sys.path.append('tests/channels/pjsip/subscriptions/rls')

from abc import ABCMeta, abstractmethod
from rls_validation import ValidationInfo

LOGGER = logging.getLogger(__name__)


class RLSElement(object):
    """Base class for an RLS element."""

    __metaclass__ = ABCMeta

    def __init__(self, data):
        """Constructor.

        keyword Arguments:
        data                   -- The raw element from the packet message body.
        """

        self.data = data
        self.children = []
        self.content_id = {}
        self.rlmi_content_id = {}

    def handle_error(self, reason=None):
        """Handler for validation errors.

        Keyword Arguments"
        reason                 -- The failure reason. (Optional.)

        Returns:
        False.
        """

        self.reset()
        if reason is not None:
            LOGGER.error(reason)
        return False

    def count_parts(self, packet_type):
        """Count the number of child elements of a given type.

        Keyword Arguments:
        packet_type            -- The type of element to query.

        Returns:
        The count of elements matching the provided packet type.
        """

        parts = self.data.body.parts
        return sum([1 for x in parts if x.body.packet_type == packet_type])

    def get_rlmi(self):
        """Helper method to get the RLMI part for this RLSElement instance.

        Returns:
        The RLMI part of the message, if successful. Otherwise, returns None.
        """

        for part in self.data.body.parts:
            if part.body.packet_type == "RLMI":
                return part
        return None

    def validate_element(self, element, info):
        """Validates a single body element with its appropriate validator.

        Keyword Arguments:
        element                -- The packet body element to validate.
        info                   -- The ValidationInfo instance containing data
                                  for this validation session.

        Returns:
        True if the component matched expectations. Otherwise, returns False.
        """

        rls_element = None
        rls_type = element.body.packet_type

        if rls_type == "RLMI":
            rls_element = RMLI(element.body.list_elem)
        elif rls_type == "PIDF":
            rls_element = PIDF(element.body)
        elif rls_type == "MWI":
            rls_element = MWI(element.body)
        elif rls_type == "Multipart":
            rls_element = Multipart(element)
        else:
            message = (
                "Validation failed. Received unrecognized body part packet "
                "type of '{0}'.").format(rls_type)
            return self.handle_error(message)

        if not rls_element.validate(info):
            return False

        self.children.append(rls_element)
        return True

    def reset(self):
        """Resets the state of this RLSElement instance."""

        self.content_id = {}
        self.children = []

    @abstractmethod
    def validate(self, info):
        """Validates the integrity of this RLSElement instance.

        Keyword Arguments:
        info                   -- The ValidationInfo instance containing data
                                  for this validation session.

        Returns:
        True if this Multipart instance is valid. Otherwise, returns False.
        """

        pass

    @property
    def resource_cids(self):
        """The Content-ID elements for this RLSElement instance."""

        content_ids = self.content_id
        for child in self.children:
            content_ids.update(child.resource_cids)
        return content_ids

    @property
    def rlmi_cids(self):
        """The RLMI Content-ID elements for this RLSElement instance."""

        rlmi_cids = self.rlmi_content_id
        for child in self.children:
            rlmi_cids.update(child.rlmi_cids)
        return rlmi_cids

class Multipart(RLSElement):
    """General class that validates a multipart body of an RLS packet."""

    def __init__(self, multi_part):
        """Constructor.

        Keyword Arguments:
        multi_part             -- The Multipart part from a multipart body.
        """

        super(Multipart, self).__init__(multi_part)

    def validate(self, info):
        """Validates the integrity of a Multipart body.

        This filters down through parts within the multipart body
        in order to recursively evaluate each element contained
        within.

        Keyword Arguments:
        info                   -- The ValidationInfo instance containing data
                                  for this validation session.

        Returns:
        True if this Multipart instance is valid. Otherwise, returns False.
        """

        LOGGER.debug("Validating multipart body...")

        content_id = self.data.content_id
        rlmi = self.get_rlmi()

        if not self.__validate_content_id(content_id):
            return False

        if not self.__validate_rlmi_element(rlmi):
            return False

        self.content_id[rlmi.body.list_elem.uri] = content_id
        name = rlmi.body.list_elem.name[0].valueOf_
        next_resource = info.resources.get(name)
        resources = next_resource["sublist"]

        if not self.__validate_next_resource(next_resource, name):
            return False

        return self.__validate_children(info, resources, rlmi, name)

    def __validate_children(self, info, resources, rlmi, name):
        """Validates the children elements of a Multipart body.

        Keyword Arguments:
        info                   -- The ValidationInfo instance containing data
                                  for this validation session.
        resources              -- The 'sublist' element of the next_resource
                                  for the Multipart body.
        rlmi                   -- The raw RLMI section of the Multipart body.
        name                   -- The name of the next resource.

        Returns:
        True if the validation is successful. Otherwise, returns False.
        """

        multipart_info = ValidationInfo(resources,
                                        info.version,
                                        info.fullstate,
                                        rlmi,
                                        name)

        for part in self.data.body.parts:
            if not self.validate_element(part, multipart_info):
                return self.handle_error()

        return True

    def __validate_content_id(self, content_id):
        """Verifies the Multipart body contains exactly one Content-ID element.

        Keyword Arguments:
        content_id             -- The raw Content-ID element.

        Returns:
        True if the validation is successful. Otherwise, returns False.
        """

        LOGGER.debug("Processing multipart body -- Inspecting "
                     "'Content-ID' element...")

        if not content_id:
            message = (
                "Processing multipart body -- Validation check failed. "
                "Multipart does not have a 'Content-ID' element.")
            return self.handle_error(message)

        LOGGER.debug("Processing multipart body -- Validation check "
                     "passed. Received expected 'Content-ID' element.")

        return True

    def __validate_next_resource(self, next_resource, name):
        """Verifies there is only one RLMI element of an Multipart body.

        Keyword Arguments:
        next_resource          -- The next resource in the expectations list.
        name                   -- The expected name of the next resource.

        Returns:
        True if the validation is successful. Otherwise, returns False.
        """

        LOGGER.debug("Processing multipart body -- Inspecting body for: "
                     "resource: ({0})...".format(name))

        if not next_resource:
            message = (
                "Processing multipart body -- Validation check failed. "
                "Received unexpected resource ({0}) in RLMI message "
                "body.").format(name)
            return self.handle_error(message)

        LOGGER.debug("Processing multipart body -- Validation check "
                     "passed. Resource ({0}) is an expected "
                     "resource.".format(name))

        # Verifying next resource type is 'Multipart'
        LOGGER.debug("Processing multipart body -- Inspecting resource "
                     "({0}) type attribute. Expecting: "
                     "'Multipart'...".format(name))

        next_type = next_resource["type"]
        if  next_type != "Multipart":
            message = (
                "Processing multipart body -- Validation check failed. "
                "Expected packet type to be 'Multipart' but received "
                "({0}).").format(next_type)
            return self.handle_error(message)

        LOGGER.debug("Processing multipart body -- Validation check "
                     "passed. Received expected packet type.".format(name))

        return True

    def __validate_rlmi_element(self, rlmi):
        """Verifies there is only one RLMI element of an Multipart body.

        Keyword Arguments:
        rlmi                   -- The raw RLMI elements.

        Returns:
        True if the validation is successful. Otherwise, returns False.
        """

        LOGGER.debug("Processing multipart body -- Inspecting RLMI part...")

        if rlmi is None:
            message = (
                "Processing multipart body -- Validation check failed. "
                "Multipart does not contain expected RLMI part.")
            return self.handle_error(message)

        LOGGER.debug("Processing multipart body -- Validation check "
                     "passed. Received expected RLMI part.")

        return True

class MWI(RLSElement):
    """General class that validates an MWI body from an RLS packet."""

    def __init__(self, mwi_body):
        """Constructor.

        Keyword Arguments:
        mwi_body               -- The MWI body from a multipart body.
        """

        super(MWI, self).__init__(mwi_body)

    def validate(self, info):
        """Validates the integrity of an MWI body.

        This uses the RLMI that included the MWI body such that its
        name and URI can be determined and linked to the appropriate
        resource.

        Keyword Arguments:
        info                   -- The ValidationInfo instance containing data
                                  for this validation session.

        Returns:
        True if this MWI instance is valid. Otherwise, returns False.
        """

        LOGGER.debug("Validating MWI body ...")

        if not self.__validate_content_id(self.data.content_id):
            return False

        res_name = None
        res_uri = None

        for resource in info.rlmi.body.list_elem.resource:
            if resource.instance[0].cid == self.data.content_id:
                res_name = resource.name[0].valueOf_
                res_uri = resource.uri
                break

        if not self.__validate_rlmi_body(info):
            return False
        if not self.__validate_resource_instance(res_name, res_uri):
            return False
        if not self.__validate_mwi_resource(info, res_name):
            return False

        self.content_id[res_uri] = self.data.content_id
        return True

    def __validate_content_id(self, content_id):
        """Verifies the MWI body contains exactly one Content-ID element.

        Keyword Arguments:
        content_id             -- The raw Content-ID element.

        Returns:
        True if the validation is successful. Otherwise, returns False.
        """

        LOGGER.debug("Processing MWI body -- Inspecting 'Content-ID' "
                     "element...")

        if not content_id:
            message = (
                "Processing MWI body -- Validation check failed. MWI body "
                "does not contain a Content-ID.")
            return self.handle_error(message)

        LOGGER.debug("Processing MWI body -- Validation check passed. MWI body"
                     "contains a Content-ID.")

        return True

    def __validate_mwi_resource(self, info, name):
        """Validates the MWI resource of an MWI body.

        Keyword Arguments:
        info                   -- The ValidationInfo instance containing data
                                  for this validation session.
        name                   -- The name of the MWI resource instance.

        Returns:
        True if the validation is successful. Otherwise, returns False.
        """

        LOGGER.debug("Processing MWI body -- Inspecting MWI resource...")

        relevant_resource = info.resources.get(name)

        if not relevant_resource:
            message = (
                "Processing MWI body -- Validation check failed. MWI '{0}' "
                "not specified in expected resources.").format(name)
            return self.handle_error(message)

        resource_type = relevant_resource["type"]

        if resource_type != "MWI":
            message = (
                "Processing MWI body -- Validation check failed. Resource "
                "type ({0}) isn't an MWI type.").format(resource_type)
            return self.handle_error(message)

        actual_vm = relevant_resource["voice_message"]
        expected_vm = self.data.voice_message

        if actual_vm != expected_vm:
            message = (
                "Processing MWI body -- Validation check failed. Received "
                "Voice-Message header ({0}) doesn't match expected "
                "({1}).").format(actual_vm, expected_vm)
            return self.handle_error(message)

        actual_msgs_waiting = relevant_resource["messages_waiting"]
        expected_msgs_waiting = self.data.messages_waiting

        if actual_msgs_waiting != expected_msgs_waiting:
            message = (
                "Processing MWI body -- Validation check failed. Received "
                "Messages-Waiting header ({0}) doesn't match expected "
                "({1}).").format(actual_msgs_waiting, expected_msgs_waiting)
            return self.handle_error(message)

        LOGGER.debug("Processing MWI body -- Validation check passed for MWI "
                     "resource ({0}).".format(relevant_resource))

        return True

    def __validate_resource_instance(self, name, uri):
        """Validates the RLMI body has a resource instance for this MWI body.

        Keyword Arguments:
        name                   -- The name of the MWI resource instance.
        uri                    -- The URI of the MWI resource instance.

        Returns:
        True if the validation is successful. Otherwise, returns False.
        """

        LOGGER.debug("Processing MWI body -- Inspecting RLMI body resource "
                     "instances...")

        if not name:
            message = (
                "Processing MWI body -- Validation check failed. "
                "Couldn't find MWI body with Content ID '{0}' in "
                "RLMI body.").format(self.data.content_id)
            return self.handle_error(message)

        if not uri:
            message = (
                "Processing MWI body -- Validation check failed. URI not "
                "found for resource '{0}' in RLMI body.").format(name)
            return self.handle_error(message)

        LOGGER.debug("Processing MWI body -- Validation check passed. RLMI "
                     "body contains a resource instance for this MWI body.")

        return True

    def __validate_rlmi_body(self, info):
        """Validates the MWI body contains an RLMI body.

        Keyword Arguments:
        info                   -- The ValidationInfo instance containing data
                                  for this validation session.

        Returns:
        True if the validation is successful. Otherwise, returns False.
        """

        LOGGER.debug("Processing MWI body -- Inspecting RLMI body...")

        if not info.rlmi:
            message = (
                "Processing MWI body -- Validation check failed. MWI "
                "part does not contain an RLMI body.")
            return self.handle_error(message)

        LOGGER.debug("Processing MWI body -- Validation check passed. MWI "
                     "part contains an RLMI body.")

        return True

class PIDF(RLSElement):
    """General class that validates the PIDF body of an RLS packet."""

    def __init__(self, pidf_body):
        """Constructor.

        Keyword Arguments:
        pidf_body              -- The PIDF body from a multipart body.
        """

        super(PIDF, self).__init__(pidf_body)

    def validate(self, info):
        """Validates the integrity of a PIDF body.

        This uses XML ElementTree to parse the PIDF body and ensures basic
        structural elements (as they relate to RLS) are present.

        Keyword Arguments:
        info                   -- The ValidationInfo instance containing data
                                  for this validation session.

        Returns:
        True if this PIDF instance is valid. Otherwise, returns False.
        """

        LOGGER.debug("Validating PIDF body ...")

        if not self.__validate_content_id(self.data.content_id):
            return False

        uri = self.__try_parse_uri()
        if not uri:
            return False

        self.content_id[uri] = self.data.content_id
        return True

    def __validate_content_id(self, content_id):
        """Verifies the PIDF body contains exactly one Content-ID element.

        Keyword Arguments:
        content_id             -- The raw Content-ID element.

        Returns:
        True if the validation is successful. Otherwise, returns False.
        """

        LOGGER.debug("Processing PIDF body -- Inspecting 'Content-ID' "
                     "element...")

        if not content_id:
            message = (
                "Processing PIDF body -- Validation check failed. "
                "PIDF body does not contain a Content-ID.")
            return self.handle_error(message)

        LOGGER.debug("Processing PIDF body -- Validation check passed. "
                     "PIDF body contains a Content-ID.")

        return True

    def __try_parse_uri(self):
        """Tries to parse the URI from the PIDF XML.

        Returns:
        The URI if successful. Otherwise, returns False.
        """

        try:
            root = ET.fromstring(self.data.xml)
        except Exception as ex: HERE
            message = (
                "Processing PIDF body -- Validation check failed."
                "Exception when parsing PIDF XML: {0}.").format(ex)
            return self.handle_error(message)

        entity = root.get("entity")
        if not entity:
            message = (
                "Processing PIDF body -- Validation check failed. "
                "PIDF document root has no entity element.")
            return self.handle_error(message)

        return entity.strip("<>")

class RMLI(RLSElement):
    """General class that validates the RLMI part of an RLS packet."""

    def __init__(self, list_elem):
        """Constructor.

        Keyword Arguments:
        list_elem              -- The XML <list> element in the RLMI body, as
                                  parsed by lxml.


        """

        super(RMLI, self).__init__(list_elem)

    def validate(self, info):
        """Validates an RLMI document.

        This method checks the integrity of the list element and calls
        into a helper method to check the integrity of each resource
        element in the list.

        Keyword Arguments:
        info                   -- The ValidationInfo instance containing data
                                  for this validation session.

        Returns:
        True if this RMLI instance is valid. Otherwise, returns
        False.
        """

        LOGGER.debug("Validating RLMI list element...")

        #if not self.__validate_version(info):
        #    return False

        if not self.__validate_fullstate(info):
            return False

        if not self.__validate_name():
            return False

        if not self.__validate_resources(info):
            return False

        if not self.__validate_rlmi_name(info):
            return False

        return self.__validate_rlmi_resources(info)

    def __validate_fullstate(self, info):
        """Verifies the RLMI body contains the expected fullstate value.

        Keyword Arguments:
        info                   -- The ValidationInfo instance containing data
                                  for this validation session.

        Returns:
        True if the validation is successful. Otherwise, returns False.
        """

        LOGGER.debug("Processing RLMI list element -- Inspecting RLMI "
                     "fullstate value. Expecting: "
                     "{0}...".format(info.fullstate))

        list_fullstate = self.data.get_fullState()

        if list_fullstate != info.fullstate:
            message = (
                "Processing RLMI list element --  Validation "
                "check failed. Received unexpected RLMI fullState "
                "value ({0}).").format(list_fullstate)
            return self.handle_error(message)

        LOGGER.debug("Processing RLMI list element -- Validation check "
                     "passed. Received expected RLMI fullstate value.")
        return True

    def __validate_name(self):
        """Verifies the RLMI body contains exactly one name element.

        Returns:
        True if the validation is successful. Otherwise, returns False.
        """

        LOGGER.debug("Processing RLMI list element -- Inspecting number "
                     "of 'name' elements. Expecting: 1.")

        list_name = self.data.get_name()

        if len(list_name) != 1:
            message = (
                "Processing RLMI list element -- Validation "
                "check failed. Received unexpected number of "
                "'name' elements ({0}).").format(len(list_name))
            return self.handle_error(message)

        LOGGER.debug("Processing RLMI list element -- Validation check "
                     "passed. Received expected number of 'name' elements.")

        return True

    def __validate_resources(self, info):
        """Verifies the RLMI body contains the expected number of resources.

        Keyword Arguments:
        info                   -- The ValidationInfo instance containing data
                                  for this validation session.

        Returns:
        True if the validation is successful. Otherwise, returns False.
        """

        LOGGER.debug("Processing RLMI list element -- Inspecting number "
                     "of 'resource' elements. Expecting: "
                     "{0}.".format(len(info.resources)))

        list_resources = self.data.resource
        res_count = len(list_resources)

        if res_count != len(info.resources):
            message = (
                "Processing RLMI list element -- Validation "
                "check failed. Received unexpected number of "
                "'resource' elements ({0}).").format(res_count)
            return self.handle_error(message)

        LOGGER.debug("Processing RLMI list element -- Validation check "
                     "passed. Received expected number of 'resource' "
                     "elements.")

        return True

    def __validate_rlmi_resources(self, info):
        """Validates each RLMI resources from the RLMI body.

        This method checks the integrity of the each RLMI resource element in
        the RLMI list.

        Keyword Arguments:
        info                   -- The ValidationInfo instance containing data
                                  for this validation session.

        Returns:
        True if the validation is successful. Otherwise, returns False.
        """

        LOGGER.debug("Processing RLMI list element -- Validating children "
                     "RLMI resource elements.")

        for resource in self.data.resource:
            rlmi_resource = RLMIResource(resource)
            if not rlmi_resource.validate(info):
                return self.handle_error()
            self.children.append(rlmi_resource)
        return True

    def __validate_rlmi_name(self, info):
        """Verifies the RLMI body contains exactly one Content-ID element.

        Keyword Arguments:
        info                   -- The ValidationInfo instance containing data
                                  for this validation session.

        Returns:
        True if the validation is successful. Otherwise, returns False.
        """

        LOGGER.debug("Processing RLMI list element -- Inspecting RLMI list "
                     "name. Expecting: {0}.".format(info.rlmi_name))

        list_name = self.data.get_name()

        if list_name[0].get_valueOf_() != info.rlmi_name:
            message = (
                "Processing RLMI list element -- Validation check "
                "failed. Received unexpected RLMI list name "
                "({0}).").format(self.data.name[0].value())
            return self.handle_error(message)

        LOGGER.debug("Processing RLMI list element -- Validation check "
                     "passed. Received expected RLMI list name.")

        return True

    def __validate_version(self, info):
        """Verifies the RLMI body contains exactly one Content-ID element.

        Keyword Arguments:
        info                   -- The ValidationInfo instance containing data
                                  for this validation session.

        Returns:
        True if the validation is successful. Otherwise, returns False.
        """

        LOGGER.debug("Processing RLMI list element -- Inspecting RLMI "
                     "version. Expecting: {0}...".format(info.version))

        list_version = self.data.get_version()

        if list_version != info.version:
            message = (
                "Processing RLMI list element -- Validation check failed. "
                "Received unexpected RLMI version ({0}).").format(list_version)
            return self.handle_error(message)

        LOGGER.debug("Processing RLMI list element -- Validation check "
                     "passed. Received expected RLMI version.")

        return True

class RLMIResource(RLSElement):
    """General class that validates an RLMI resource."""

    def __init__(self, rlmi_resource):
        """Constructor.

        Keyword Arguments:
        rlmi_resource          -- The XML <resource> element in the RLMI
                                  <list>, as parsed by lxml.
        """

        super(RLMIResource, self).__init__(rlmi_resource)

    def validate(self, info):
        """Validate an RLMI resource.

        This method checks the integrity of a resource XML element within an
        RLMI list.

        Keyword Arguments:
        info                   -- The ValidationInfo instance containing data
                                  for this validation session.

        Returns:
        True if the validation is successful. Otherwise, returns False.
        """

        LOGGER.debug("Validating RLMI resource...")

        if not self.__validate_uri():
            return False

        if not self.__validate_name(info):
            return False

        if not self.__validate_instance(info):
            return False

        self.rlmi_content_id[self.data.uri] = self.data.instance[0].cid
        return True

    def __validate_instance(self, info):
        """Validates the instance attribute of this RLMI resource.

        Keyword Arguments:
        info                   -- The ValidationInfo instance containing data
                                  for this validation session.
        Returns:
        True if the validation is successful. Otherwise, returns False.
        """

        LOGGER.debug("Processing RLMI resource -- Inspecting number of "
                     "'instance' elements. Expecting: 1.")

        instances = len(self.data.instance)
        if instances != 1:
            message = (
                "Processing RLMI resource -- Validation check "
                "failed. Received unexpected number of 'instance' "
                "elements ({0}) in RLMI resource.").format(instances)
            return self.handle_error(message)

        LOGGER.debug("Processing RLMI resource -- Validation check passed. "
                     "Received expected number of 'instance' elements.")

        # Validate RLMI resource instance attribute
        LOGGER.debug("Processing RLMI resource -- Inspecting RLMI resource "
                     "instance attributes: state, id, and cid...")

        resource_instance = self.data.instance[0]

        if not resource_instance.state:
            message = (
                "Processing RLMI resource -- Validation check "
                "failed. Resource instance has no state.")
            return self.handle_error(message)
        if not resource_instance.id:
            message = (
                "Processing RLMI resource -- Validation check "
                "failed. Resource instance has no id.")
            return self.handle_error(message)
        if not resource_instance.cid:
            message = (
                "Processing RLMI resource -- Validation check "
                "failed. Resource instance has no cid.")
            return self.handle_error(message)

        LOGGER.debug("Processing RLMI resource -- Validation check passed. "
                     "Received values for 'instance' element attributes: "
                     "state, id and cid.")

        # Validate the instance state matches the expected value
        name = self.data.get_name()[0].get_valueOf_()
        state = info.resources[name]["state"]
        LOGGER.debug("Processing RLMI resource -- Inspecting instance "
                     "state. Expecting: {0}...".format(state))

        if resource_instance.state != state:
            message = (
                "Processing RLMI resource -- Validation check failed. "
                "Received unexpected instance state "
                "({0})).").format(resource_instance.state)
            return self.handle_error(message)

        LOGGER.debug("Processing RLMI resource -- Validation check passed. "
                     "Received expected value for the RLMI instance state.")

        return True

    def __validate_name(self, info):
        """Validates the name for this RLMI resource.

        The method first ensures the RLMI resource contains only one name
        element. Then, inspects the value of the name element to ensure it
        was an expected resource.

        Keyword Arguments:
        info                   -- The ValidationInfo instance containing data
                                  for this validation session.

        Returns:
        True if the validation is successful. Otherwise, returns False.
        """

        LOGGER.debug("Processing RLMI resource -- Inspecting number of "
                     "'name' elements. Expecting: 1.")

        resource_name = self.data.get_name()

        if len(resource_name) != 1:
            message = (
                "Processing RLMI resource -- Validation check "
                "failed. Received unexpected number of 'name' "
                "elements ({0}).").format(len(resource_name))
            return self.handle_error(message)

        LOGGER.debug("Processing RLMI resource -- Validation check "
                     "passed. Received expected number of 'name' elements.")

        LOGGER.debug("Processing RLMI resource -- Inspecting RLMI "
                     "resource name...")

        name = resource_name[0].get_valueOf_()

        if name not in info.resources:
            message = (
                "Processing RLMI resource -- Validation check "
                "failed. Received unexpected RLMI resource name "
                "({0}).").format(name)
            return self.handle_error(message)

        LOGGER.debug("Processing RLMI list element -- Validation check "
                     "passed. Received expected RLMI resource name.")

        return True

    def __validate_uri(self):
        """Validates the URI attribute of this RLMI resource.

        Returns:
        True if the validation is successful. Otherwise, returns False.
        """

        LOGGER.debug("Processing RLMI resource -- Inspecting 'uri' "
                     "attribute... ")

        if not self.data.uri:
            message = (
                "Processing RLMI resource -- Validation check "
                "failed. RLMI resource is missing its 'uri' attribute.")
            return self.handle_error(message)

        LOGGER.debug("Processing RLMI resource -- Validation check "
                   "passed. Received expected 'uri' attribute.")
        return True

class RLSPacket(RLSElement):
    """General class that validates a multipart RLS NOTIFY body."""

    def __init__(self, packet):
        """Constructor.

        Keyword Arguments:
        packet                 -- The Multipart NOTIFY body in full.
        """

        super(RLSPacket, self).__init__(packet)

    def validate(self, info):
        """Validates a multipart RLS packet.

        If the multipart body does not pass validation, then the test will
        fail. If this method returns at all, it means that the body passed
        validation.

        Keyword Arguments:
        info                   -- The ValidationInfo instance containing data
                                  for this validation session.

        Returns:
        True if the multipart RLS packet matches the expectations provided at
        construction. Otherwise, returns False.
        """

        LOGGER.debug("Validating RLS packet...")

        if not self.__validate_part_counts(info):
            return False

        if not self.__validate_children(info):
            return False

        return self.__validate_content_ids()

    def __validate_part_counts(self, info):
        """Validates the body and RLMI part counts of an RLS packet.

        Keyword Arguments:
        info                   -- The ValidationInfo instance containing data
                                  for this validation session.

        Returns:
        True if the validation is successful. Otherwise, returns False.
        """

        LOGGER.debug("Processing RLS packet -- Inspecting number of "
                     "body parts received. Expecting: "
                     "{0}...".format(len(info.resources)))

        body_parts = len(self.data.body.parts)

        if body_parts != len(info.resources) + 1:
            message = (
                "Processing RLS packet -- Validation check failed. "
                "Received unexpected number of parts ({0}) in "
                "multipart body.").format(body_parts - 1)
            return self.handle_error(message)

        LOGGER.debug("Processing RLS packet -- Validation check passed. "
                     "Received expected number of body parts.")

        # Verify there is exactly 1 RLMI part
        LOGGER.debug("Processing RLS packet -- Inspecting number of RMLI "
                     "parts received. Expecting: 1...")

        rlmi_parts = self.count_parts("RLMI")

        if rlmi_parts != 1:
            message = (
                "Processing RLS packet -- Validation check failed. "
                "Received unexpected number of RLMI parts ({0}) in "
                "multipart body.").format(rlmi_parts)
            return self.handle_error(message)

        LOGGER.debug("Processing RLS packet -- Validation check passed. "
                     "Received expected number of RMLI parts.")

        return True

    def __validate_children(self, info):
        """Validates the children elements of an RLS packet.

        Keyword Arguments:
        info                   -- The ValidationInfo instance containing data
                                  for this validation session.

        Returns:
        True if the validation is successful. Otherwise, returns False.
        """

        rlmi = self.get_rlmi()
        rls_info = ValidationInfo(info.resources,
                                  info.version,
                                  info.fullstate,
                                  rlmi,
                                  info.rlmi_name)

        for part in self.data.body.parts:
            if not self.validate_element(part, rls_info):
                return self.handle_error()

        return True

    def __validate_content_ids(self):
        """Validates the Content-IDs of an RLS packet.

        Returns:
        True if the validation is successful. Otherwise, returns False.
        """

        resource_cids = self.resource_cids
        rlmi_cids = self.rlmi_cids

        LOGGER.debug("Processing RLS packet -- Inspecting number of "
                     "Content-IDs received. Expecting: "
                     "{0}...".format(len(resource_cids)))

        if len(rlmi_cids) != len(resource_cids):
            message = (
                "Processing RLS packet -- Validation check failed. "
                "Gathered mismatching number of Content IDs. RLMI "
                "document has {0} Content IDs but was expected to "
                "have {1}.").format(len(rlmi_cids),
                                    len(resource_cids))
            return self.handle_error(message)

        LOGGER.debug("Processing RLS packet -- Validation check passed. "
                     "Received expected number of Content IDs.")

        for uri, cid in rlmi_cids.iteritems():
            if uri not in resource_cids:
                message = (
                    "Processing RLS packet -- Validation check "
                    "failed. URI {0} not found within the RLS packet "
                    "Content-ID elements.").format(uri)
                return self.handle_error(message)

            resource_cid = resource_cids.get(uri)
            if resource_cid != cid:
                message = (
                    "Processing RLS packet -- Validation check failed. "
                    "Mismatching Content-ID for URI ({0}). RLMI document has "
                    "({1}). Document has ({2})").format(uri,
                                                        cid,
                                                        resource_cid)
                return self.handle_error(message)
        return True
