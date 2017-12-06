These files can be used by any tests needing them.  They were
created using the gen_ca_and_certs script which recreates all
keys and certs.

There are 2 subdirectories ca1 and ca2.  This allows asterisk to
use keys from different CAs to test verification.

This directory (configs/keys) is ignored by the configs install
function to prevent the files from being unnecessarily copied to
every test in the testsuite.  To use them from individual tests,
simply create RELATIVE symlinks or copy to your test's
configs/astX directory. They'll then be copied automatically to the
test's etc/asterisk directory. To reference them from other config
files, use the "<<astetcdir>>" replaceable parameter.

Example:

$ cd tests/channels/pjsip/mytest/configs/ast1
$ ln -s ln -s ../../../../../../configs/keys/ca1/ca1.crt
$ ln -s ln -s ../../../../../../configs/keys/ca1/ca1-ast1.crt
$ ln -s ln -s ../../../../../../configs/keys/ca1/ca1-ast1.key

Then edit tests/channels/pjsip/mytest/configs/ast1/pjsip.conf
and add a transport...

[local-transport-tls]
type = transport
protocol = tls
method = tlsv1
cipher = AES128-CCM <snip>
priv_key_file = <<astetcdir>>/ast1.key
cert_file = <<astetcdir>>/ast1.crt
ca_list_file = <<astetcdir>>/ca1.crt
verify_client = no
verify_server = no
require_client_cert = no
async_operations = 20
bind = 127.0.0.1:5061

If you need to use more than 1 ca cert file, either copy or link to the
ca-bundle.crt file or link or copy both ca1.crt and ca2.crt to your directory
and run:
$ c_rehash .

This will create the necessary links to use the directory as a "path":
ca_list_path = <<astetcdir>>/


