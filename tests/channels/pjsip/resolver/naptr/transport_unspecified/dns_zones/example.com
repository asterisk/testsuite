zone = [
    SOA(
        # For whom we are the authority
        'example.com',

        # This nameserver's name
        mname = "ns1.example.com",

        # Mailbox of individual who handles this
        rname = "root.example.com",

        # Unique serial identifying this SOA data
        serial = 2003010601,

        # Time interval before zone should be refreshed
        refresh = "1H",

        # Interval before failed refresh should be retried
        retry = "1H",

        # Upper limit on time interval before expiry
        expire = "1H",

        # Minimum TTL
        minimum = "1H"
    ),

    NAPTR('naptr.example.com', 0, 1, 'S', 'SIP+D2T', '', '_sip._tcp.example.com'),
    NAPTR('naptr.example.com', 0, 2, 'S', 'SIP+D2U', '', '_sip._udp.example.com'),
    SRV('_sip._tcp.example.com', 0, 1, 5061, 'pbx.example.com'),
    SRV('_sip._udp.example.com', 0, 1, 5061, 'pbx.example.com'),
    A('pbx.example.com', '127.0.0.1'),
]
