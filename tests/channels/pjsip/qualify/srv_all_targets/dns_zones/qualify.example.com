zone = [
    SOA(
        'qualify.example.com',
        mname = 'ns1.qualify.example.com',
        rname = 'root.qualify.example.com',
        serial = 2026072201,
        refresh = '1H',
        retry = '1H',
        expire = '1H',
        minimum = '1H'
    ),

    # Nothing binds the preferred target.  If qualify only uses the first SRV
    # result, the contact will time out and be marked unreachable.
    SRV('_sip._udp.qualify.example.com', 0, 1, 5061,
        'silent.qualify.example.com'),
    SRV('_sip._udp.qualify.example.com', 1, 1, 5062,
        'answering.qualify.example.com'),
    A('silent.qualify.example.com', '127.0.0.2'),
    A('answering.qualify.example.com', '127.0.0.1'),
]
