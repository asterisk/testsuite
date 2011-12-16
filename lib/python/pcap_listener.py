from twisted.internet import abstract, protocol
from yappcap import PcapLive, findalldevs

class PcapFile(abstract.FileDescriptor):
    """Treat a live pcap capture as a file for Twisted to call select() on"""
    def __init__(self, protocol, interface, filter=None, dumpfile=None):
        abstract.FileDescriptor.__init__(self)

        p = PcapLive(interface, autosave=dumpfile)
        p.activate()
        p.blocking = False

        if filter is not None:
            p.setfilter(filter)

        self.pcap = p
        self.fd = p.fileno
        self.protocol = protocol
        self.protocol.makeConnection(self)
        self.startReading()

    def fileno(self):
        return self.fd

    def doRead(self):
        pkt = self.pcap.next()

        # we may not have a packet if something weird happens
        if not pkt:
            # according to the twisted docs 0 implies no write done
            return 0

        self.protocol.dataReceived(pkt)

    def connectionLost(self, reason):
        self.protocol.connectionLost(reason)


class PcapListener(protocol.Protocol):
    """A Twisted protocol wrapper for a pcap capture"""
    def __init__(self, interface, bpf_filter=None, dumpfile=None, callback=None):
        """Initialize a new PcapListener

        interface - The name of an interface. If None, the first loopback interface
        bpf_filter - A Berkeley packet filter, i.e. "udp port 5060"
        dumpfile - The filename where to save the capture file
        callback - A function that will receive a PcapPacket for each packet captured

        """
        if interface is None:
            interface = [x.name for x in findalldevs() if x.loopback][0]
        self.pf = PcapFile(self, interface, bpf_filter, dumpfile)
        self.callback = callback

    def makeConnection(self, transport):
        self.connectionMade()

    def dataReceived(self, data):
        if self.callback:
            self.callback(data)
