from twisted.internet import abstract, protocol
import logging
import scapy
from scapy.all import *
from scapy.config import conf
import socket
import os

LOGGER = logging.getLogger(__name__)

class PcapListener():
    """A A wrapper for a scapy pcap capture"""
    def __init__(self, interface, bpf_filter=None, dumpfile=None,
                 callback=None, snaplen=None, buffer_size=None):
        """Initialize a new PcapListener

        interface - The name of an interface. If None, the first loopback interface
        bpf_filter - A Berkeley packet filter, i.e. "udp port 5060"
        dumpfile - The filename where to save the capture file
        callback - A function that will receive a PcapPacket for each packet captured
        snaplen - Number of bytes to capture from each packet. If None, then
                  65535.
        buffer_size - The ring buffer size. If None, then 0.

        """

        if interface is None:
            interface = self.find_first_loopback_device()
        if buffer_size is None:
            buffer_size = 8192
        if snaplen is None:
            snaplen = 65535
        self.pcap_writer = None

        scapy.config.conf.use_pcap = True
        self.callback = callback

        LOGGER.info("Starting capture.  if: %s dumpfile: %s snap: %d  bs: %d",
                    interface, dumpfile, snaplen, buffer_size)

        if dumpfile is not None:
            self.pcap_writer = PcapWriter(dumpfile, sync=True,
                nano=True, snaplen=snaplen, bufsz=buffer_size)

        self.pf = AsyncSniffer(iface=interface,filter=bpf_filter,
            prn=self._callback)

        self.pf.start()

    def _callback(self, packet: scapy.packet.Packet):
        if self.callback:
            self.callback(packet.original)

        if self.pcap_writer:
            self.pcap_writer.write(packet)
        return None

    def find_first_loopback_device(self):
        iflist = scapy.interfaces.get_working_ifaces()
        for i in iflist:
            if "LOOPBACK" in i.flags and "UP" in i.flags:
                return i.name
        return None
