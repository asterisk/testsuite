#!/usr/bin/env python
"""Demonstration of parsing and printing RLMI XML document.

This script is meant to demonstrate how, given an RLMI XML document, one can use
the pyxb-generated rlmi module to parse the XML document into easy-to peruse
objects. The XML document used in this demo is from RFC 4662, section 5.1.

This script must be run from the base testsuite directory since paths are assumed to
originate from there.
"""

import sys

sys.path.append("lib/python")

# rlmi is a pyxb-generated module create from the XML schema for RLMI. It
# defines classes that are used when an RLMI XML document is parsed.
import rlmi

xml = open('contrib/scripts/rlmi.xml').read()
# CreateFromDocument takes XML text and creates an XML document object that can
# be used in ways that Python objects are typically used.
list_elem = rlmi.CreateFromDocument(xml)

# The outermost XML element in an RLMI document is the 'list' element.
print('list')
# pyxb performs type-checking and type conversion of elements that it comes
# across in XML documents. In this case, the list element's version attribute is
# an integer, and the fullState attribute is a boolean. This is why the str()
# function is necessary in order to convert to string for the concatenation.
print('\t' + str(list_elem.version))
print('\t' + str(list_elem.fullState))
print('\t' + list_elem.uri)
# A list element may have zero or more name elements in it. This is a
# user-visible name for the list. The main reason why more than one name may
# exist for a list would be because it is expressed in multiple languages.
# Asterisk RLMI lists will have only a single name.
for name in list_elem.name:
    print('\tname')
    # Parsed XML documents have their attributes accessed as members on an
    # object.
    print('\t\t' + name.lang)
    # The content of XML elements is accessed through the value() member.
    print('\t\t' + name.value())
# A list element may have zero or more resource elements in it. The resources
# represent the resources that make up the list (duh).
for resource in list_elem.resource:
    print('\tresource')
    print('\t\t' + resource.uri)
    # Resources may have names associated with them, just like the list does.
    # Asterisk will use the name of the list from the configuration file here.
    for name in resource.name:
        print('\t\tname')()
        print('\t\t\t' + name.value())
    # Resources may have zero or more instance elements on them. The reason that
    # more than one instance element may exist for a resource is that a resource
    # may correspond to a single subscription that forks, resulting in multiple
    # instances of the resource being represented. In Asterisk's case, there
    # will be a single instance per resource.
    for instance in resource.instance:
        print('\t\tinstance')
        print('\t\t\t' + instance.id)
        print('\t\t\t' + instance.state)
        # If an instance has a cid, it indicates that there is a body element
        # in the multipart body that corresponds to the instance. The cid
        # corresponds to the Content-ID header in that body part.
        if instance.cid:
            print('\t\t\t' + instance.cid)
