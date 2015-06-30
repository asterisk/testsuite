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

    SRV('_sip._udp.example.com', 1, 0, 5063, 'slow.pbx.example.com'),
    SRV('_sip._tcp.example.com', 0, 0, 5062, 'fast.pbx.example.com'),

    A('fast.pbx.example.com', '127.0.0.1'),
    A('slow.pbx.example.com', '127.0.0.1'),
]
