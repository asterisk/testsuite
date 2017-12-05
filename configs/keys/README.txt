These files can be used by any tests needing them.  They were
created using the ast_tls_cert script located in the asterisk
source directory under contrib/scripts.  The password for the
ca.key files is 'cakey'.

Example:
ast_tls_cert -C 127.0.0.1 -O ast1 -o ast1

There are 2 subdirectories ca1 and ca2.  This allows asterisk to
use keys from different CAs to test verification.

This directory (configs/keys) is ignored by the configs install
function to prevent the files from being unnecessarily copied to
every test in the testsuite.  To use them from individual tests,
simply create RELATIVE symlinks to them from your test's
configs/astX directory. They'll then be copied automatically to the
test's etc/asterisk directory. To reference them from other config
files, use the "<<astetcdir>>" replaceable parameter.

Example:

$ cd tests/channels/pjsip/mytest/configs/ast1
$ ln -s ln -s ../../../../../../configs/keys/ca1/ca.crt
$ ln -s ln -s ../../../../../../configs/keys/ca1/ast1.crt
$ ln -s ln -s ../../../../../../configs/keys/ca1/ast1.key

Then edit tests/channels/pjsip/mytest/configs/ast1/pjsip.conf
and add a transport...

[local-transport-tls]
type = transport
protocol = tls
method = tlsv1
cipher = AES128-CCM <snip>
priv_key_file = <<astetcdir>>/ast1.key
cert_file = <<astetcdir>>/ast1.crt
ca_list_file = <<astetcdir>>/ca.crt
verify_client = no
verify_server = no
require_client_cert = no
async_operations = 20
bind = 127.0.0.1:5061

You can also use the chain.pem file if you need the ca.crt files
from both ca1 and ca2.
