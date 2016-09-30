[global]
type=global
debug=yes

[transport]
type=transport
protocol=udp
bind=127.0.0.1

[endpoint_t](!)
type=endpoint
context=default
direct_media=no
from_domain=127.0.0.1
;media_address=127.0.0.1

[audio]
type=aor
max_contacts=1
contact=sip:audio@127.0.0.1:5060

[audio_endpoint_t](!,endpoint_t)
aors=audio
from_user=audio
