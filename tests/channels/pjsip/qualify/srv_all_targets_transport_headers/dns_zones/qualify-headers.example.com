zone = [
    SOA(
        'qualify-headers.example.com',
        mname = 'ns1.qualify-headers.example.com',
        rname = 'root.qualify-headers.example.com',
        serial = 2026072301,
        refresh = '1H',
        retry = '1H',
        expire = '1H',
        minimum = '1H'
    ),

    SRV('_sip._tcp.qualify-headers.example.com', 0, 1, 5061,
        'first.qualify-headers.example.com'),
    SRV('_sip._tcp.qualify-headers.example.com', 1, 1, 5062,
        'second.qualify-headers.example.com'),
    A('first.qualify-headers.example.com', '127.0.0.1'),
    A('second.qualify-headers.example.com', '127.0.0.1'),
]
