# certs generated using the following commands:

# create CA
openssl req -x509 -days 999999 -newkey rsa:4096 -nodes -keyout ca.key -out ca.crt

# create server key and signing request
openssl req -newkey rsa:4096 -nodes -keyout uas.key -out uas.csr -subj="/C=US/CN=*.example.com"

# create server certificate
openssl x509 -days 999999 -CAkey ca.key -CA ca.crt -in uas.csr -set_serial 01 -req -out uas.crt

# create client key and signing request
openssl req -newkey rsa:4096 -nodes -keyout uac.key -out uac.csr -subj="/C=US/CN=uac.example.com"

# create server certificate
openssl x509 -days 999999 -CAkey ca.key -CA ca.crt -in uac.csr -set_serial 01 -req -out uac.crt
