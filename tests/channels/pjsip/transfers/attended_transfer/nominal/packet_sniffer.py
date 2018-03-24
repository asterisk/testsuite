#!/usr/bin/env python
"""Pluggable module that generates AMI UserEvents based on packets sniffed.

This will generate AMI UserEvents based on specific SIP packets that have been
sniffed. Some SIP messages are used to determine if a call leg gets remotely
bridged or if a remote bridge is torn down. It determines this by examining
packets containing INVITE and 200 OK messages, using call states, and SIP/RTP
ports for a specific scenario.

An AMI UserEvent is generated when:
* it's been determined that a remote bridge is setup on two call legs
* it's been determined that a remote bridge is torn down on a call leg
* a sipfrag NOTIFY is sniffed
* a REFER is sniffed
* a 491 Request Pending is sniffed

This is for a specific scenario of nominal local attended transfers where
direct media, hold, and REFER w/Replaces is used. It may also be specific to
only work when using pjsua clients and chan_pjsip.

This does not set a pass/fail result. The UserEvents are used by other modules
to set the test's result.

Copyright (C) 2015, Digium, Inc.
John Bigelow <jbigelow@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
"""

import sys
import logging
from twisted.internet import reactor, task
import pjsua as pj

sys.path.append('lib/python')

from asterisk.phones import PjsuaPhoneController
from asterisk.pcap import VOIPListener

LOGGER = logging.getLogger(__name__)


class Sniffer(VOIPListener):
    """Pluggable module class derived from pcap.VOIPListener.

    This examines SIP packets for INVITE, 200 OK, REFER, NOTIFY, and 491
    Request Pending messages. It determines if a remote RTP bridge has been
    setup or torn down for call leg(s). When a determination is made it will
    generate an AMI UserEvent indicating what was determined. It also generates
    an AMI UserEvent when a REFER, NOTIFY sipfrag, and a 491 Request
    Pending are found.
    """
    def __init__(self, module_config, test_object):
        """Create listener, add callback, and add AMI observer.

        Keyword Arguments:
        module_config Dict of module configuration
        test_object Test object
        """
        self.set_pcap_defaults(module_config)
        VOIPListener.__init__(self, module_config, test_object)

        self.test_object = test_object
        self.ami = None
        self.test_object.register_ami_observer(self.ami_connect)
        self.add_callback('SIP', self.__check_sip_packet)
        self.calls = {'alice': [], 'bob': [], 'charlie': []}

    def set_pcap_defaults(self, module_config):
        """Set default PcapListener config that isn't explicitly overridden.

        Keyword Arguments:
        module_config Dict of module configuration
        """
        pcap_defaults = {'device': 'lo', 'snaplen': 2000,
                         'bpf-filter': 'udp port 5060', 'debug-packets': True,
                         'buffer-size': 4194304, 'register-observer': True}
        for name, value in pcap_defaults.items():
            module_config[name] = module_config.get(name, value)

    def ami_connect(self, ami):
        """Callback when AMI connects. Sets AMI instance.

        Keyword Arguments:
        ami AMI instance
        """
        self.ami = ami

    def __check_sip_packet(self, packet):
        """Callback function for when we have a SIP packet

        Check if SIP packet is an INVITE or 200 OK message.

        Keyword Arguments:
        packet A SIP packet
        """
        if (('INVITE' in packet.request_line or
             '200 OK' in packet.request_line or
             'NOTIFY' in packet.request_line) and not packet.body):
            return

        if 'INVITE' in packet.request_line:
            self.check_invite(packet)
        elif '200 OK' in packet.request_line:
            self.check_200(packet)
        elif 'REFER' in packet.request_line:
            self.check_refer(packet)
        elif 'NOTIFY' in packet.request_line:
            self.check_notify(packet)
        elif '491 Request Pending' in packet.request_line:
            self.hold_reinvite_race(packet)

    def get_rtp_data(self, packet):
        """Get the RTP port associated with this packet

        Keyword Arguments:
        packet A SIP packet

        Returns:
        Int of RTP port if found. Otherwise None.
        """
        src_ip = packet.ip_layer.header.source
        sdp_ports = self.packet_factory.get_global_data(src_ip)
        return sdp_ports.get('rtp')

    def add_call(self, packet):
        """Track a new call and set the initial state

        Must ensure call is not already being tracked before calling this and
        should only be called when an INVITE is found.

        Keyword Arguments:
        packet A SIP packet
        """
        callid = packet.headers['Call-ID']
        src_port = str(packet.transport_layer.header.source)
        dst_port = str(packet.transport_layer.header.destination)
        # We know the ports our pjsua instances are using.
        if '5061' in [src_port, dst_port]:
            self.calls['alice'].append({callid: "CONNECTING"})
        elif '5062' in [src_port, dst_port]:
            self.calls['bob'].append({callid: "CONNECTING"})
        elif '5063' in [src_port, dst_port]:
            self.calls['charlie'].append({callid: "CONNECTING"})
        else:
            LOGGER.warn("Unexpected SIP port.")
            return

        LOGGER.debug("{0}: {1}".format(callid, self.get_call_state(callid)))

    def update_call_state(self, callid, newstate):
        """Update the state of a call

        Keyword Arguments:
        callid String of the call-id to update
        newstate String of the state to set for the call
        """
        location = self.find_call(callid)
        if location is None:
            LOGGER.warn("Call not found. Unable to update call state.")
            return
        self.calls[location[0]][location[1]][callid] = newstate
        LOGGER.debug("{0}: {1}".format(callid, newstate))

    def find_call(self, callid):
        """Find the endpoint and index location of the dict for the callid

        This searches self.calls for the callid.

        Keyword Arguments:
        callid String of the call-id to search for

        Returns:
        Tuple containing the key name of self.calls and the index location of
        list where the callid is located. Otherwise None.
        """
        for endpoint, endpoint_calls in self.calls.items():
            gen = (idx for (idx, call) in enumerate(endpoint_calls)
                   if callid in call)
            call_index = next(gen, None)
            if call_index is not None:
                return (endpoint, call_index)
        return None

    def get_call_state(self, callid):
        """Get the state of a call

        Keyword Arguments:
        callid String of the call-id to search for

        Returns:
        String of call state if found. Otherwise None.
        """
        location = self.find_call(callid)
        if location is not None:
            return self.calls[location[0]][location[1]][callid]
        return None

    def check_invite(self, packet):
        """Check INVITE to determine and set the state of the call.

        Keyword Arguments:
        packet A SIP packet
        """
        callid = packet.headers['Call-ID']

        # If call is not known about, start tracking it.
        if self.find_call(callid) is None:
            self.add_call(packet)
            return

        # Call is already known
        if self.is_hold(packet):
            return

        if packet.transport_layer.header.source != 5060:
            # This shouldn't be hit since an INVITE from an endpoint is either
            # a new call or for hold.
            LOGGER.warn("Unexpected INVITE found: {0}".format(callid))
            return

        # We have an INVITE of an already known call from Asterisk (we know
        # it's using port 5060).
        if self.get_rtp_data(packet) > 10000:
            # The SDP has an RTP port within Asterisk's range (we know it uses
            # 10000-20000).
            if self.get_call_state(callid) == "RTP_RB_STARTED":
                # If the call is already in a remote RTP bridge, then this
                # INVITE means the remote RTP bridge is being torn down.
                self.update_call_state(callid, "RTP_RB_STOPPING")
            elif self.get_call_state(callid) == "HOLD_STARTED":
                # If the call is already holding (the one that had sent the
                # re-INVITE restricting media) then this INVITE is due to the
                # remote RTP bridge being torn down.
                self.update_call_state(callid, "RTP_RB_STOPPING")
        else:
            # The SDP has an RTP port not within Asterisk's range so Asterisk
            # must be initiating a remote RTP bridge.
            self.update_call_state(callid, "RTP_RB_STARTING")

    def check_200(self, packet):
        """Check 200 OK to determine and set the state of the call.

        This will then send an AMI UserEvent if two call legs are remotely
        bridged of a call leg is no longer remotely bridged.

        Keyword Arguments:
        packet A SIP packet
        """
        callid = packet.headers['Call-ID']

        if self.find_call(callid) is None:
            self.add_call(packet)
            return

        if packet.transport_layer.header.source == 5060:
            # We have a 200 OK of an already known call from Asterisk.
            if (not self.is_hold(packet) and
                    self.get_call_state(callid) == "CONNECTING"):
                # It's not due to a hold and the call is connecting. So this
                # 200 OK means it's being answered.
                self.update_call_state(callid, "CONNECTED")
            return

        # We have a 200 OK of an already known call from a pjsua endpoint.
        if self.get_call_state(callid) == "CONNECTING":
            # If the call is connecting then this 200 OK means it's being
            # answered.
            self.update_call_state(callid, "CONNECTED")
        elif self.get_call_state(callid) == "RTP_RB_STARTING":
            # If the call is already in the process of being remotely
            # bridged, then this 200 OK means the call now is.
            self.update_call_state(callid, "RTP_RB_STARTED")

            # Find all endpoints that have at least 1 call that is remotely
            # bridged.
            reinvited_endpoints = []
            for endpoint, endpoint_calls in self.calls.items():
                lst = [c for c in endpoint_calls
                       if 'RTP_RB_STARTED' in c.values()]
                if lst:
                    reinvited_endpoints.append(endpoint)
            LOGGER.debug("Endpoints in remote RTP bridge: {0}"
                         .format(reinvited_endpoints))

            # Only send event if two are in a remote RTP bridge. Even though
            # it's not known if these are up with each other, we assume they
            # are since it's a specific scenario.
            if len(reinvited_endpoints) == 2:
                event_data = {}
                # Build dict for the UserEvent.
                for num, endpoint in enumerate(reinvited_endpoints):
                    k = "Endpoint{0}".format(num + 1)
                    event_data[k] = endpoint
                self.send_user_event('RemoteRTPBridgeStarted', event_data)
        elif self.get_call_state(callid) == "RTP_RB_STOPPING":
            # If the call is already in the process of having a remote RTP
            # bridge being torn down, then this 200 OK means it now is.
            self.update_call_state(callid, "RTP_RB_STOPPED")
            event_data = {}
            event_data['Endpoint1'] = self.find_call(callid)[0]
            # Send event for each.
            self.send_user_event('RemoteRTPBridgeStopped', event_data)

    def check_refer(self, packet):
        """Get header values from REFER and send an AMI UserEvent.

        This will send an AMI UserEvent with the values of the Refer-To &
        Referred-By headers.

        Keyword Arguments:
        packet A SIP packet
        """
        event_data = {}
        event_data['ReferTo'] = packet.headers.get('Refer-To')
        event_data['ReferredBy'] = packet.headers.get('Referred-By')
        self.send_user_event('ReferInfo', event_data)

    def check_notify(self, packet):
        """Check NOTIFY for sipfrag refer event.

        This will then parse a sipfrag NOTIFY and send an AMI UserEvent
        containing the body of the message.

        Keyword Arguments:
        packet A SIP packet
        """
        event_data = {}
        callid = packet.headers['Call-ID']

        if self.find_call(callid) is None:
            return
        if packet.body.packet_type != "message/sipfrag":
            return
        if "refer" not in packet.headers['Event']:
            return
        if packet.transport_layer.header.source != 5060:
            return

        ascii_pkt = packet.ascii_packet
        last_pos = ascii_pkt.find('\r\n', ascii_pkt.find('Content-Length'))
        event_data['NotifyBody'] = packet.ascii_packet[last_pos:].strip()
        self.send_user_event('NotifySIPFrag', event_data)

    def is_hold(self, packet):
        """If INVITE or 200 OK message then check if it corresponds to a hold

        Keyword Arguments:
        packet A SIP packet

        Returns:
        True if it corresponds to a hold. False otherwise.
        """
        callid = packet.headers['Call-ID']
        for line in packet.body.sdp_lines:
            if 'INVITE' in packet.request_line:
                if 'a=sendonly' in line:
                    self.update_call_state(callid, "HOLD_STARTING")
                    return True
            elif '200 OK' in packet.request_line:
                if 'a=recvonly' in line:
                    self.update_call_state(callid, "HOLD_STARTED")
                    return True
        return False

    def hold_reinvite_race(self, packet):
        """Get endpoint from From header and generate UserEvent.

        The previous hold attempt was not actually successfull as a 491 SIP
        message was found. Generate a UserEvent with info.

        Keyword Arguments:
        packet A SIP packet
        """
        LOGGER.debug("Race between hold and reinvite found.")
        for endpoint in self.calls.keys():
            if endpoint in packet.headers['From']:
                break
        self.send_user_event('491RequestPending', {'PjsuaAccount': endpoint})

    def send_user_event(self, user_event, event_data):
        """Send AMI UserEvent

        Keyword Arguments:
        user_event String of user event name
        event_data Dict containing event headers and values
        """
        LOGGER.debug("Sending UserEvent '{0}'".format(user_event))
        self.ami.userEvent(user_event, **event_data)


def hold(test_object, triggered_by, source, event):
    """Override of phones.hold()

    The phones.hold() method checks if a hold is already in progress or not.
    When a 491 occurs the hold will remain in progress as pjsua doesn't raise
    an exception or change any state. This allows bypassing the checks so a
    hold can be attempted again.

    Keyword Arguments:
    test_object Test object
    triggered_by Object that triggered this callback
    source AMI instance
    event Dictionary of AMI event causing the trigger

    Returns:
    True
    """
    def __handle_error(reason):
        """Callback handler for twisted deferred errors.

        Handle twisted deferred errors. If it's due to a PJsua invalid
        operation then retry the hold. Otherwise stop the reactor and raise the
        error.

        Keyword Arguments:
        reason Instance of Failure for the reason of the error
        """
        if reason.check(pj.Error):
            if "PJ_EINVALIDOP" in reason.value.err_msg():
                __retry()
            else:
                test_object.stop_reactor()
                raise Exception("Exception: '{0}'".format(str(reason)))
        else:
            test_object.stop_reactor()
            raise Exception("Exception: '{0}'".format(str(reason)))

    def __retry():
        """Retry placing the call on hold.

        Create a deferred to handle errors and schedule retry.
        """
        task.deferLater(reactor, .25,
                        phone.hold_call).addErrback(__handle_error)

    controller = PjsuaPhoneController.get_instance()
    phone = controller.get_phone_obj(name=event['pjsuaaccount'])

    try:
        phone.hold_call()
    except pj.Error as err:
        if "PJ_EINVALIDOP" in err.err_msg():
            # Create a deferred to handle errors and schedule to try placing
            # the call on hold again.
            task.deferLater(reactor, .25,
                            phone.hold_call).addErrback(__handle_error)
        else:
            test_object.stop_reactor()
            raise Exception("Exception: '{0}'".format(str(err)))
    except:
        test_object.stop_reactor()
        raise Exception("Exception: '{0}'".format(str(sys.exc_info())))

    return True
