zone = [
    SOA(
        'qualify-addresses.example.com',
        mname = 'ns1.qualify-addresses.example.com',
        rname = 'root.qualify-addresses.example.com',
        serial = 2026072301,
        refresh = '1H',
        retry = '1H',
        expire = '1H',
        minimum = '1H'
    ),

    # List the unresponsive address first in each set.
    A('a-udp.qualify-addresses.example.com', '127.0.0.2'),
    A('a-udp.qualify-addresses.example.com', '127.0.0.1'),
    AAAA('aaaa-udp.qualify-addresses.example.com', '::2'),
    AAAA('aaaa-udp.qualify-addresses.example.com', '::1'),
    A('a-tcp.qualify-addresses.example.com', '127.0.0.2'),
    A('a-tcp.qualify-addresses.example.com', '127.0.0.1'),
    A('a-tcp-selected.qualify-addresses.example.com', '127.0.0.2'),
    A('a-tcp-selected.qualify-addresses.example.com', '127.0.0.1'),
]
