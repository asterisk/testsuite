from twisted.internet import abstract, protocol
from yappcap import PcapLive, findalldevs, PcapTimeout


class PcapFile(abstract.FileDescriptor):
    """Treat a live pcap capture as a file for Twisted to call select() on"""
    def __init__(self, protocol, interface, xfilter=None, dumpfile=None,
                 snaplen=65535, buffer_size=0):
        abstract.FileDescriptor.__init__(self)

        p = PcapLive(interface, autosave=dumpfile, snaplen=snaplen,
                     buffer_size=buffer_size, timeout=1000)
        p.activate()
        p.blocking = False

        if xfilter is not None:
            p.filter = xfilter

        self.pcap = p
        self.fd = p.fileno
        self.protocol = protocol
        self.protocol.makeConnection(self)
        self.startReading()

    def fileno(self):
        return self.fd

    def doRead(self):
        try:
            pkt = next(self.pcap)
        except PcapTimeout:
            return 0

        # we may not have a packet if something weird happens
        if not pkt:
            # according to the twisted docs 0 implies no write done
            return 0

        self.protocol.dataReceived(pkt)

    def connectionLost(self, reason):
        self.protocol.connectionLost(reason)


class PcapListener(protocol.Protocol):
    """A Twisted protocol wrapper for a pcap capture"""
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
            interface = [x.name for x in findalldevs() if x.loopback][0]
        if buffer_size is None:
            buffer_size = 0
        if snaplen is None:
            snaplen = 65535
        self.pf = PcapFile(self, interface, bpf_filter, dumpfile, snaplen,
                           buffer_size)
        self.callback = callback

    def makeConnection(self, transport):
        self.connectionMade()

    def dataReceived(self, data):
        if self.callback:
            self.callback(data)
