# ./rlmi.py
# -*- coding: utf-8 -*-
# PyXB bindings for NM:3e5578c8ec4c38e134207ce683adb060f503853f
# Generated 2014-06-10 12:31:07.911934 by PyXB version 1.2.3
# Namespace urn:ietf:params:xml:ns:rlmi

import pyxb
import pyxb.binding
import pyxb.binding.saxer
import io
import pyxb.utils.utility
import pyxb.utils.domutils
import sys

# Unique identifier for bindings created at the same time
_GenerationUID = pyxb.utils.utility.UniqueIdentifier('urn:uuid:01af2fb6-f0c5-11e3-9594-00219b028e33')

# Version of PyXB used to generate the bindings
_PyXBVersion = '1.2.3'
# Generated bindings are not compatible across PyXB versions
if pyxb.__version__ != _PyXBVersion:
    raise pyxb.PyXBVersionError(_PyXBVersion)

# Import bindings for namespaces imported into schema
import pyxb.binding.xml_
import pyxb.binding.datatypes

# NOTE: All namespace declarations are reserved within the binding
Namespace = pyxb.namespace.NamespaceForURI(u'urn:ietf:params:xml:ns:rlmi', create_if_missing=True)
Namespace.configureCategories(['typeBinding', 'elementBinding'])

def CreateFromDocument (xml_text, default_namespace=None, location_base=None):
    """Parse the given XML and use the document element to create a
    Python instance.

    @param xml_text An XML document.  This should be data (Python 2
    str or Python 3 bytes), or a text (Python 2 unicode or Python 3
    str) in the L{pyxb._InputEncoding} encoding.

    @keyword default_namespace The L{pyxb.Namespace} instance to use as the
    default namespace where there is no default namespace in scope.
    If unspecified or C{None}, the namespace of the module containing
    this function will be used.

    @keyword location_base: An object to be recorded as the base of all
    L{pyxb.utils.utility.Location} instances associated with events and
    objects handled by the parser.  You might pass the URI from which
    the document was obtained.
    """

    if pyxb.XMLStyle_saxer != pyxb._XMLStyle:
        dom = pyxb.utils.domutils.StringToDOM(xml_text)
        return CreateFromDOM(dom.documentElement)
    if default_namespace is None:
        default_namespace = Namespace.fallbackNamespace()
    saxer = pyxb.binding.saxer.make_parser(fallback_namespace=default_namespace, location_base=location_base)
    handler = saxer.getContentHandler()
    xmld = xml_text
    if isinstance(xmld, unicode):
        xmld = xmld.encode(pyxb._InputEncoding)
    saxer.parse(io.BytesIO(xmld))
    instance = handler.rootObject()
    return instance

def CreateFromDOM (node, default_namespace=None):
    """Create a Python instance from the given DOM node.
    The node tag must correspond to an element declaration in this module.

    @deprecated: Forcing use of DOM interface is unnecessary; use L{CreateFromDocument}."""
    if default_namespace is None:
        default_namespace = Namespace.fallbackNamespace()
    return pyxb.binding.basis.element.AnyCreateFromDOM(node, default_namespace)


# Atomic simple type: [anonymous]
class STD_ANON (pyxb.binding.datatypes.string, pyxb.binding.basis.enumeration_mixin):

    """An atomic simple type."""

    _ExpandedName = None
    _XSDLocation = pyxb.utils.utility.Location('/usr/src/asterisk/trunk/shit.xsd', 44, 8)
    _Documentation = None
STD_ANON._CF_enumeration = pyxb.binding.facets.CF_enumeration(value_datatype=STD_ANON, enum_prefix=None)
STD_ANON.active = STD_ANON._CF_enumeration.addEnumeration(unicode_value=u'active', tag=u'active')
STD_ANON.pending = STD_ANON._CF_enumeration.addEnumeration(unicode_value=u'pending', tag=u'pending')
STD_ANON.terminated = STD_ANON._CF_enumeration.addEnumeration(unicode_value=u'terminated', tag=u'terminated')
STD_ANON._InitializeFacetMap(STD_ANON._CF_enumeration)

# Complex type [anonymous] with content type ELEMENT_ONLY
class CTD_ANON (pyxb.binding.basis.complexTypeDefinition):
    """Complex type [anonymous] with content type ELEMENT_ONLY"""
    _TypeDefinition = None
    _ContentTypeTag = pyxb.binding.basis.complexTypeDefinition._CT_ELEMENT_ONLY
    _Abstract = False
    _ExpandedName = None
    _XSDLocation = pyxb.utils.utility.Location('/usr/src/asterisk/trunk/shit.xsd', 8, 4)
    _ElementMap = {}
    _AttributeMap = {}
    # Base type is pyxb.binding.datatypes.anyType
    
    # Element {urn:ietf:params:xml:ns:rlmi}resource uses Python identifier resource
    __resource = pyxb.binding.content.ElementDeclaration(pyxb.namespace.ExpandedName(Namespace, u'resource'), 'resource', '__urnietfparamsxmlnsrlmi_CTD_ANON_urnietfparamsxmlnsrlmiresource', True, pyxb.utils.utility.Location('/usr/src/asterisk/trunk/shit.xsd', 24, 2), )

    
    resource = property(__resource.value, __resource.set, None, None)

    
    # Element {urn:ietf:params:xml:ns:rlmi}name uses Python identifier name
    __name = pyxb.binding.content.ElementDeclaration(pyxb.namespace.ExpandedName(Namespace, u'name'), 'name', '__urnietfparamsxmlnsrlmi_CTD_ANON_urnietfparamsxmlnsrlminame', True, pyxb.utils.utility.Location('/usr/src/asterisk/trunk/shit.xsd', 58, 2), )

    
    name = property(__name.value, __name.set, None, None)

    
    # Attribute uri uses Python identifier uri
    __uri = pyxb.binding.content.AttributeUse(pyxb.namespace.ExpandedName(None, u'uri'), 'uri', '__urnietfparamsxmlnsrlmi_CTD_ANON_uri', pyxb.binding.datatypes.anyURI, required=True)
    __uri._DeclarationLocation = pyxb.utils.utility.Location('/usr/src/asterisk/trunk/shit.xsd', 15, 6)
    __uri._UseLocation = pyxb.utils.utility.Location('/usr/src/asterisk/trunk/shit.xsd', 15, 6)
    
    uri = property(__uri.value, __uri.set, None, None)

    
    # Attribute version uses Python identifier version
    __version = pyxb.binding.content.AttributeUse(pyxb.namespace.ExpandedName(None, u'version'), 'version', '__urnietfparamsxmlnsrlmi_CTD_ANON_version', pyxb.binding.datatypes.unsignedInt, required=True)
    __version._DeclarationLocation = pyxb.utils.utility.Location('/usr/src/asterisk/trunk/shit.xsd', 16, 6)
    __version._UseLocation = pyxb.utils.utility.Location('/usr/src/asterisk/trunk/shit.xsd', 16, 6)
    
    version = property(__version.value, __version.set, None, None)

    
    # Attribute fullState uses Python identifier fullState
    __fullState = pyxb.binding.content.AttributeUse(pyxb.namespace.ExpandedName(None, u'fullState'), 'fullState', '__urnietfparamsxmlnsrlmi_CTD_ANON_fullState', pyxb.binding.datatypes.boolean, required=True)
    __fullState._DeclarationLocation = pyxb.utils.utility.Location('/usr/src/asterisk/trunk/shit.xsd', 18, 6)
    __fullState._UseLocation = pyxb.utils.utility.Location('/usr/src/asterisk/trunk/shit.xsd', 18, 6)
    
    fullState = property(__fullState.value, __fullState.set, None, None)

    
    # Attribute cid uses Python identifier cid
    __cid = pyxb.binding.content.AttributeUse(pyxb.namespace.ExpandedName(None, u'cid'), 'cid', '__urnietfparamsxmlnsrlmi_CTD_ANON_cid', pyxb.binding.datatypes.string)
    __cid._DeclarationLocation = pyxb.utils.utility.Location('/usr/src/asterisk/trunk/shit.xsd', 20, 6)
    __cid._UseLocation = pyxb.utils.utility.Location('/usr/src/asterisk/trunk/shit.xsd', 20, 6)
    
    cid = property(__cid.value, __cid.set, None, None)

    _AttributeWildcard = pyxb.binding.content.Wildcard(process_contents=pyxb.binding.content.Wildcard.PC_lax, namespace_constraint=pyxb.binding.content.Wildcard.NC_any)
    _ElementMap.update({
        __resource.name() : __resource,
        __name.name() : __name
    })
    _AttributeMap.update({
        __uri.name() : __uri,
        __version.name() : __version,
        __fullState.name() : __fullState,
        __cid.name() : __cid
    })



# Complex type [anonymous] with content type ELEMENT_ONLY
class CTD_ANON_ (pyxb.binding.basis.complexTypeDefinition):
    """Complex type [anonymous] with content type ELEMENT_ONLY"""
    _TypeDefinition = None
    _ContentTypeTag = pyxb.binding.basis.complexTypeDefinition._CT_ELEMENT_ONLY
    _Abstract = False
    _ExpandedName = None
    _XSDLocation = pyxb.utils.utility.Location('/usr/src/asterisk/trunk/shit.xsd', 25, 4)
    _ElementMap = {}
    _AttributeMap = {}
    # Base type is pyxb.binding.datatypes.anyType
    
    # Element {urn:ietf:params:xml:ns:rlmi}instance uses Python identifier instance
    __instance = pyxb.binding.content.ElementDeclaration(pyxb.namespace.ExpandedName(Namespace, u'instance'), 'instance', '__urnietfparamsxmlnsrlmi_CTD_ANON__urnietfparamsxmlnsrlmiinstance', True, pyxb.utils.utility.Location('/usr/src/asterisk/trunk/shit.xsd', 36, 2), )

    
    instance = property(__instance.value, __instance.set, None, None)

    
    # Element {urn:ietf:params:xml:ns:rlmi}name uses Python identifier name
    __name = pyxb.binding.content.ElementDeclaration(pyxb.namespace.ExpandedName(Namespace, u'name'), 'name', '__urnietfparamsxmlnsrlmi_CTD_ANON__urnietfparamsxmlnsrlminame', True, pyxb.utils.utility.Location('/usr/src/asterisk/trunk/shit.xsd', 58, 2), )

    
    name = property(__name.value, __name.set, None, None)

    
    # Attribute uri uses Python identifier uri
    __uri = pyxb.binding.content.AttributeUse(pyxb.namespace.ExpandedName(None, u'uri'), 'uri', '__urnietfparamsxmlnsrlmi_CTD_ANON__uri', pyxb.binding.datatypes.anyURI, required=True)
    __uri._DeclarationLocation = pyxb.utils.utility.Location('/usr/src/asterisk/trunk/shit.xsd', 32, 6)
    __uri._UseLocation = pyxb.utils.utility.Location('/usr/src/asterisk/trunk/shit.xsd', 32, 6)
    
    uri = property(__uri.value, __uri.set, None, None)

    _AttributeWildcard = pyxb.binding.content.Wildcard(process_contents=pyxb.binding.content.Wildcard.PC_lax, namespace_constraint=pyxb.binding.content.Wildcard.NC_any)
    _ElementMap.update({
        __instance.name() : __instance,
        __name.name() : __name
    })
    _AttributeMap.update({
        __uri.name() : __uri
    })



# Complex type [anonymous] with content type SIMPLE
class CTD_ANON_2 (pyxb.binding.basis.complexTypeDefinition):
    """Complex type [anonymous] with content type SIMPLE"""
    _TypeDefinition = pyxb.binding.datatypes.string
    _ContentTypeTag = pyxb.binding.basis.complexTypeDefinition._CT_SIMPLE
    _Abstract = False
    _ExpandedName = None
    _XSDLocation = pyxb.utils.utility.Location('/usr/src/asterisk/trunk/shit.xsd', 59, 4)
    _ElementMap = {}
    _AttributeMap = {}
    # Base type is pyxb.binding.datatypes.string
    
    # Attribute {http://www.w3.org/XML/1998/namespace}lang uses Python identifier lang
    __lang = pyxb.binding.content.AttributeUse(pyxb.namespace.ExpandedName(pyxb.namespace.XML, 'lang'), 'lang', '__urnietfparamsxmlnsrlmi_CTD_ANON_2_httpwww_w3_orgXML1998namespacelang', pyxb.binding.xml_.STD_ANON_lang)
    __lang._DeclarationLocation = None
    __lang._UseLocation = pyxb.utils.utility.Location('/usr/src/asterisk/trunk/shit.xsd', 62, 10)
    
    lang = property(__lang.value, __lang.set, None, None)

    _ElementMap.update({
        
    })
    _AttributeMap.update({
        __lang.name() : __lang
    })



# Complex type [anonymous] with content type ELEMENT_ONLY
class CTD_ANON_3 (pyxb.binding.basis.complexTypeDefinition):
    """Complex type [anonymous] with content type ELEMENT_ONLY"""
    _TypeDefinition = None
    _ContentTypeTag = pyxb.binding.basis.complexTypeDefinition._CT_ELEMENT_ONLY
    _Abstract = False
    _ExpandedName = None
    _XSDLocation = pyxb.utils.utility.Location('/usr/src/asterisk/trunk/shit.xsd', 37, 4)
    _ElementMap = {}
    _AttributeMap = {}
    # Base type is pyxb.binding.datatypes.anyType
    
    # Attribute id uses Python identifier id
    __id = pyxb.binding.content.AttributeUse(pyxb.namespace.ExpandedName(None, u'id'), 'id', '__urnietfparamsxmlnsrlmi_CTD_ANON_3_id', pyxb.binding.datatypes.string, required=True)
    __id._DeclarationLocation = pyxb.utils.utility.Location('/usr/src/asterisk/trunk/shit.xsd', 42, 6)
    __id._UseLocation = pyxb.utils.utility.Location('/usr/src/asterisk/trunk/shit.xsd', 42, 6)
    
    id = property(__id.value, __id.set, None, None)

    
    # Attribute state uses Python identifier state
    __state = pyxb.binding.content.AttributeUse(pyxb.namespace.ExpandedName(None, u'state'), 'state', '__urnietfparamsxmlnsrlmi_CTD_ANON_3_state', STD_ANON, required=True)
    __state._DeclarationLocation = pyxb.utils.utility.Location('/usr/src/asterisk/trunk/shit.xsd', 43, 6)
    __state._UseLocation = pyxb.utils.utility.Location('/usr/src/asterisk/trunk/shit.xsd', 43, 6)
    
    state = property(__state.value, __state.set, None, None)

    
    # Attribute reason uses Python identifier reason
    __reason = pyxb.binding.content.AttributeUse(pyxb.namespace.ExpandedName(None, u'reason'), 'reason', '__urnietfparamsxmlnsrlmi_CTD_ANON_3_reason', pyxb.binding.datatypes.string)
    __reason._DeclarationLocation = pyxb.utils.utility.Location('/usr/src/asterisk/trunk/shit.xsd', 52, 6)
    __reason._UseLocation = pyxb.utils.utility.Location('/usr/src/asterisk/trunk/shit.xsd', 52, 6)
    
    reason = property(__reason.value, __reason.set, None, None)

    
    # Attribute cid uses Python identifier cid
    __cid = pyxb.binding.content.AttributeUse(pyxb.namespace.ExpandedName(None, u'cid'), 'cid', '__urnietfparamsxmlnsrlmi_CTD_ANON_3_cid', pyxb.binding.datatypes.string)
    __cid._DeclarationLocation = pyxb.utils.utility.Location('/usr/src/asterisk/trunk/shit.xsd', 54, 6)
    __cid._UseLocation = pyxb.utils.utility.Location('/usr/src/asterisk/trunk/shit.xsd', 54, 6)
    
    cid = property(__cid.value, __cid.set, None, None)

    _AttributeWildcard = pyxb.binding.content.Wildcard(process_contents=pyxb.binding.content.Wildcard.PC_lax, namespace_constraint=pyxb.binding.content.Wildcard.NC_any)
    _HasWildcardElement = True
    _ElementMap.update({
        
    })
    _AttributeMap.update({
        __id.name() : __id,
        __state.name() : __state,
        __reason.name() : __reason,
        __cid.name() : __cid
    })



list = pyxb.binding.basis.element(pyxb.namespace.ExpandedName(Namespace, u'list'), CTD_ANON, location=pyxb.utils.utility.Location('/usr/src/asterisk/trunk/shit.xsd', 7, 2))
Namespace.addCategoryObject('elementBinding', list.name().localName(), list)

resource = pyxb.binding.basis.element(pyxb.namespace.ExpandedName(Namespace, u'resource'), CTD_ANON_, location=pyxb.utils.utility.Location('/usr/src/asterisk/trunk/shit.xsd', 24, 2))
Namespace.addCategoryObject('elementBinding', resource.name().localName(), resource)

name = pyxb.binding.basis.element(pyxb.namespace.ExpandedName(Namespace, u'name'), CTD_ANON_2, location=pyxb.utils.utility.Location('/usr/src/asterisk/trunk/shit.xsd', 58, 2))
Namespace.addCategoryObject('elementBinding', name.name().localName(), name)

instance = pyxb.binding.basis.element(pyxb.namespace.ExpandedName(Namespace, u'instance'), CTD_ANON_3, location=pyxb.utils.utility.Location('/usr/src/asterisk/trunk/shit.xsd', 36, 2))
Namespace.addCategoryObject('elementBinding', instance.name().localName(), instance)



CTD_ANON._AddElement(pyxb.binding.basis.element(pyxb.namespace.ExpandedName(Namespace, u'resource'), CTD_ANON_, scope=CTD_ANON, location=pyxb.utils.utility.Location('/usr/src/asterisk/trunk/shit.xsd', 24, 2)))

CTD_ANON._AddElement(pyxb.binding.basis.element(pyxb.namespace.ExpandedName(Namespace, u'name'), CTD_ANON_2, scope=CTD_ANON, location=pyxb.utils.utility.Location('/usr/src/asterisk/trunk/shit.xsd', 58, 2)))

def _BuildAutomaton ():
    # Remove this helper function from the namespace after it is invoked
    global _BuildAutomaton
    del _BuildAutomaton
    import pyxb.utils.fac as fac

    counters = set()
    cc_0 = fac.CounterCondition(min=0L, max=None, metadata=pyxb.utils.utility.Location('/usr/src/asterisk/trunk/shit.xsd', 10, 8))
    counters.add(cc_0)
    cc_1 = fac.CounterCondition(min=0L, max=None, metadata=pyxb.utils.utility.Location('/usr/src/asterisk/trunk/shit.xsd', 12, 8))
    counters.add(cc_1)
    states = []
    final_update = set()
    final_update.add(fac.UpdateInstruction(cc_0, False))
    symbol = pyxb.binding.content.ElementUse(CTD_ANON._UseForTag(pyxb.namespace.ExpandedName(Namespace, u'name')), pyxb.utils.utility.Location('/usr/src/asterisk/trunk/shit.xsd', 10, 8))
    st_0 = fac.State(symbol, is_initial=True, final_update=final_update, is_unordered_catenation=False)
    states.append(st_0)
    final_update = set()
    final_update.add(fac.UpdateInstruction(cc_1, False))
    symbol = pyxb.binding.content.ElementUse(CTD_ANON._UseForTag(pyxb.namespace.ExpandedName(Namespace, u'resource')), pyxb.utils.utility.Location('/usr/src/asterisk/trunk/shit.xsd', 12, 8))
    st_1 = fac.State(symbol, is_initial=True, final_update=final_update, is_unordered_catenation=False)
    states.append(st_1)
    transitions = []
    transitions.append(fac.Transition(st_0, [
        fac.UpdateInstruction(cc_0, True) ]))
    transitions.append(fac.Transition(st_1, [
        fac.UpdateInstruction(cc_0, False) ]))
    st_0._set_transitionSet(transitions)
    transitions = []
    transitions.append(fac.Transition(st_1, [
        fac.UpdateInstruction(cc_1, True) ]))
    st_1._set_transitionSet(transitions)
    return fac.Automaton(states, counters, True, containing_state=None)
CTD_ANON._Automaton = _BuildAutomaton()




CTD_ANON_._AddElement(pyxb.binding.basis.element(pyxb.namespace.ExpandedName(Namespace, u'instance'), CTD_ANON_3, scope=CTD_ANON_, location=pyxb.utils.utility.Location('/usr/src/asterisk/trunk/shit.xsd', 36, 2)))

CTD_ANON_._AddElement(pyxb.binding.basis.element(pyxb.namespace.ExpandedName(Namespace, u'name'), CTD_ANON_2, scope=CTD_ANON_, location=pyxb.utils.utility.Location('/usr/src/asterisk/trunk/shit.xsd', 58, 2)))

def _BuildAutomaton_ ():
    # Remove this helper function from the namespace after it is invoked
    global _BuildAutomaton_
    del _BuildAutomaton_
    import pyxb.utils.fac as fac

    counters = set()
    cc_0 = fac.CounterCondition(min=0L, max=None, metadata=pyxb.utils.utility.Location('/usr/src/asterisk/trunk/shit.xsd', 27, 8))
    counters.add(cc_0)
    cc_1 = fac.CounterCondition(min=0L, max=None, metadata=pyxb.utils.utility.Location('/usr/src/asterisk/trunk/shit.xsd', 29, 8))
    counters.add(cc_1)
    states = []
    final_update = set()
    final_update.add(fac.UpdateInstruction(cc_0, False))
    symbol = pyxb.binding.content.ElementUse(CTD_ANON_._UseForTag(pyxb.namespace.ExpandedName(Namespace, u'name')), pyxb.utils.utility.Location('/usr/src/asterisk/trunk/shit.xsd', 27, 8))
    st_0 = fac.State(symbol, is_initial=True, final_update=final_update, is_unordered_catenation=False)
    states.append(st_0)
    final_update = set()
    final_update.add(fac.UpdateInstruction(cc_1, False))
    symbol = pyxb.binding.content.ElementUse(CTD_ANON_._UseForTag(pyxb.namespace.ExpandedName(Namespace, u'instance')), pyxb.utils.utility.Location('/usr/src/asterisk/trunk/shit.xsd', 29, 8))
    st_1 = fac.State(symbol, is_initial=True, final_update=final_update, is_unordered_catenation=False)
    states.append(st_1)
    transitions = []
    transitions.append(fac.Transition(st_0, [
        fac.UpdateInstruction(cc_0, True) ]))
    transitions.append(fac.Transition(st_1, [
        fac.UpdateInstruction(cc_0, False) ]))
    st_0._set_transitionSet(transitions)
    transitions = []
    transitions.append(fac.Transition(st_1, [
        fac.UpdateInstruction(cc_1, True) ]))
    st_1._set_transitionSet(transitions)
    return fac.Automaton(states, counters, True, containing_state=None)
CTD_ANON_._Automaton = _BuildAutomaton_()




def _BuildAutomaton_2 ():
    # Remove this helper function from the namespace after it is invoked
    global _BuildAutomaton_2
    del _BuildAutomaton_2
    import pyxb.utils.fac as fac

    counters = set()
    cc_0 = fac.CounterCondition(min=0L, max=None, metadata=pyxb.utils.utility.Location('/usr/src/asterisk/trunk/shit.xsd', 39, 8))
    counters.add(cc_0)
    states = []
    final_update = set()
    final_update.add(fac.UpdateInstruction(cc_0, False))
    symbol = pyxb.binding.content.WildcardUse(pyxb.binding.content.Wildcard(process_contents=pyxb.binding.content.Wildcard.PC_lax, namespace_constraint=pyxb.binding.content.Wildcard.NC_any), pyxb.utils.utility.Location('/usr/src/asterisk/trunk/shit.xsd', 39, 8))
    st_0 = fac.State(symbol, is_initial=True, final_update=final_update, is_unordered_catenation=False)
    states.append(st_0)
    transitions = []
    transitions.append(fac.Transition(st_0, [
        fac.UpdateInstruction(cc_0, True) ]))
    st_0._set_transitionSet(transitions)
    return fac.Automaton(states, counters, True, containing_state=None)
CTD_ANON_3._Automaton = _BuildAutomaton_2()

