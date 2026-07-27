zone = [
    SOA(
        'qualify-5xx.example.com',
        mname = 'ns1.qualify-5xx.example.com',
        rname = 'root.qualify-5xx.example.com',
        serial = 2026072201,
        refresh = '1H',
        retry = '1H',
        expire = '1H',
        minimum = '1H'
    ),

    SRV('_sip._udp.qualify-5xx.example.com', 0, 1, 5061,
        'rejecting.qualify-5xx.example.com'),
    SRV('_sip._udp.qualify-5xx.example.com', 1, 1, 5062,
        'answering.qualify-5xx.example.com'),
    A('rejecting.qualify-5xx.example.com', '127.0.0.1'),
    A('answering.qualify-5xx.example.com', '127.0.0.1'),
]

