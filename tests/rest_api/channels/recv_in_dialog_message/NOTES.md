# recv_in_dialog_message — Test Notes

## Status

Currently **FAILING** — expected. Documents a known gap in COR-3928.

## What This Tests

When a remote SIP endpoint sends an in-dialog SIP MESSAGE to Asterisk on a
Stasis-controlled channel, the Stasis app should receive a `TextMessageReceived`
ARI event.

Currently this does NOT happen. See:
`~/src/asterisk-commend/asterisk/rx-in-dialog-message-gap.md`

## Why It Fails

`incoming_in_dialog_request()` in `res/res_pjsip_messaging.c` calls
`ast_msg_data_queue_frame()` which queues `AST_FRAME_TEXT_DATA` on the channel.
Stasis has no handler for this frame type — no ARI event fires.

## Fix Required

New public function `stasis_app_dispatch_message(endpoint_id, json_msg)` in
`res/stasis/messaging.c`. Called from `incoming_in_dialog_request` after
building the message data. Fires `TextMessageReceived` to subscribed ARI apps.

## Test Cases To Add Once Fixed

- `plain_text_success` — text/plain body
- `json_body_success` — application/json body
- `no_stasis_app` — channel not in Stasis, no crash
- `channel_hangup_before_message` — no crash on hangup race

## Reference

- Patch: `debian/patches/commend/0001-COR-3928-ari-add-channel-message-send-and-delivery-s.patch`
- Existing TX tests: `tests/rest_api/channels/send_message/`
