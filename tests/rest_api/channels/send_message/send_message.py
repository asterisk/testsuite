"""
Copyright (C) 2026

Tests for the ARI channel sendMessage flow.
"""

import json
import logging

import requests

from twisted.internet import reactor

from asterisk.sipp import SIPpScenario

LOGGER = logging.getLogger(__name__)


class SendMessageScenario(object):
    """Coordinate a full sendMessage test cycle."""

    def __init__(self, module_config, test_object):
        self.config = module_config
        self.test_object = test_object
        self.ari = test_object.ari

        self.scenarios = []
        self.channel_id = None
        self.channel_name = None
        self.channel_destroyed = False
        self.pending_delete = False
        self.unexpected_delivery_events = []
        self._completed = False

        self.requests = []
        self.sent_count = 0
        self.seen_event_count = 0

        self.send_mode = self.config.get('send-mode', 'sequential')
        self.start_delay = float(self.config.get('start-delay', 1.0))
        self.send_delay = float(self.config.get('send-delay', 0.2))
        self.quiet_time = float(self.config.get('quiet-time', 1.0))
        self.wait_for_stasis = self.config.get('wait-for-stasis', True)
        self.pre_send_action = self.config.get('pre-send-action')
        self.waiting_for_snoop = False
        self.pjsip_channel_id = None

        for index, request_config in enumerate(self.config.get('requests', [])):
            request_id = request_config.get('request_id', 'send-message-%d' % (index + 1))
            params = dict(request_config.get('params') or {})
            params['request_id'] = request_id

            request = {
                'request_id': request_id,
                'params': params,
                'json_body': request_config.get('json-body'),
                'expect': request_config.get('expect', 202),
                'event_count': request_config.get('event-count', 1),
                'event': dict(request_config.get('event') or {}),
                'sent': False,
                'events_seen': 0,
                'response_ok': False,
            }

            if request['json_body'] is not None and 'body' not in request['event']:
                sip_body = request['json_body']
                request['event']['body'] = json.dumps(sip_body, separators=(',', ':'))
            elif 'body' in params and 'body' not in request['event']:
                request['event']['body'] = params['body']

            if 'content_type' in params and 'content_type' not in request['event']:
                request['event']['content_type'] = params['content_type']

            self.requests.append(request)

        load_count = int(self.config.get('load-count', 0))
        if load_count and not self.requests:
            for i in range(1, load_count + 1):
                request_id = 'load-msg-%d' % i
                self.requests.append({
                    'request_id': request_id,
                    'params': {
                        'request_id': request_id,
                        'content_type': 'text/plain',
                        'body': 'Load test message %d' % i,
                    },
                    'json_body': None,
                    'expect': 202,
                    'event_count': 1,
                    'event': {'status': 'delivered', 'sip_status_code': 200, 'reason': 'OK'},
                    'sent': False,
                    'events_seen': 0,
                    'response_ok': False,
                })

        self.test_object.register_ami_observer(self._on_ami_connection)
        self.test_object.register_ws_event_handler(self._on_ws_event)
        self.test_object.register_stop_observer(self._on_stop)

    def _on_ami_connection(self, ami):
        if ami.id != 0:
            return

        for scenario_def in self.config.get('sipp', []):
            scenario = SIPpScenario(self.test_object.test_name, scenario_def)
            self.scenarios.append(scenario)
            scenario.run(self.test_object)

        originate = self.config.get('originate')
        if originate:
            reactor.callLater(self.start_delay, self._originate, originate)

    def _originate(self, originate):
        path = self.config.get('originate-path', 'channels')
        response = self.ari.post(path, **originate)
        if response.status_code // 100 != 2:
            LOGGER.error("Originate failed: %d %s", response.status_code, response.text)
            self.test_object.set_passed(False)
            self.test_object.stop_reactor()
            return

        channel = response.json()
        if self.wait_for_stasis:
            self.channel_id = None
            self.channel_name = None
        else:
            self.channel_id = channel.get('id')
            self.channel_name = channel.get('name')

        if not self.wait_for_stasis:
            reactor.callLater(self.send_delay, self._prepare_to_send)

    def _on_ws_event(self, event):
        event_type = event.get('type')

        if event_type == 'StasisStart':
            channel = event.get('channel', {})
            if self.waiting_for_snoop and (channel.get('name') or '').startswith('Snoop/'):
                self.waiting_for_snoop = False
                self.channel_id = channel['id']
                reactor.callLater(self.send_delay, self._send_initial_requests)
                return
            if self._is_target_channel(channel):
                self.channel_id = channel['id']
                self.channel_name = channel.get('name')
                reactor.callLater(self.send_delay, self._prepare_to_send)
                return
            if self.config.get('track-all-stasis') and self.channel_id:
                LOGGER.debug("track-all-stasis: updating channel_id %s -> %s (%s)",
                             self.channel_id, channel.get('id'), channel.get('name'))
                self.channel_id = channel['id']
                return

        if event_type == 'ChannelDestroyed' and self._is_target_channel(event.get('channel')):
            self.channel_destroyed = True
            if self.pending_delete:
                self.pending_delete = False
                reactor.callLater(self.send_delay, self._send_initial_requests)
            return

        if event_type != 'ChannelMessageDeliveryStatus':
            return

        request = self._find_request(event.get('request_id'))
        if not request:
            LOGGER.error("Unexpected delivery event: %r", event)
            self.unexpected_delivery_events.append(event)
            return

        request['events_seen'] += 1
        self.seen_event_count += 1
        self._validate_delivery_event(request, event)

        if self.send_mode == 'sequential':
            self._send_next_request()
        self._maybe_finish()

    def _prepare_to_send(self):
        if self._completed:
            return

        if self.pre_send_action == 'delete_channel':
            self.pending_delete = True
            self._delete_channel()
            return

        if self.pre_send_action == 'create_snoop':
            self._create_snoop()
            return

        if self.pre_send_action == 'create_snoop_no_wait':
            self._create_snoop_no_wait()
            return

        self._send_initial_requests()

    def _send_initial_requests(self):
        if self.send_mode == 'immediate':
            for request in self.requests:
                if not request['sent']:
                    self._send_request(request)
        else:
            self._send_next_request()

        self._maybe_finish()

    def _send_next_request(self):
        for request in self.requests:
            if not request['sent']:
                self._send_request(request)
                break

    def _send_request(self, request):
        if not self.channel_id:
            LOGGER.error("No channel available for request %s", request['request_id'])
            self.test_object.set_passed(False)
            self.test_object.stop_reactor()
            return

        url = self.ari.build_url('channels', self.channel_id, 'sendMessage')
        http_body = None
        if request['json_body'] is not None:
            http_body = {'body': json.dumps(request['json_body'], separators=(',', ':'))}
        response = requests.post(
            url,
            params=request['params'],
            json=http_body,
            auth=self.ari.userpass)

        request['sent'] = True
        self.sent_count += 1

        if response.status_code != request['expect']:
            LOGGER.error(
                "Request %s expected HTTP %d, got %d %s",
                request['request_id'], request['expect'],
                response.status_code, response.text)
            self.test_object.set_passed(False)
        elif request['expect'] // 100 == 2 and response.text.strip():
            LOGGER.error("Request %s returned unexpected body %r",
                         request['request_id'], response.text)
            self.test_object.set_passed(False)
        else:
            request['response_ok'] = True

        if request['event_count'] == 0 and self._all_requests_sent():
            reactor.callLater(self.quiet_time, self._maybe_finish)

    def _validate_delivery_event(self, request, event):
        for key, expected in request['event'].items():
            actual = event.get(key)
            if actual != expected:
                LOGGER.error(
                    "Request %s expected event %s=%r, got %r",
                    request['request_id'], key, expected, actual)
                self.test_object.set_passed(False)

    def _create_snoop_no_wait(self):
        """Create Snoop then send immediately - races with Snoop's StasisStart."""
        self.pjsip_channel_id = self.channel_id
        response = self.ari.post(
            'channels', self.pjsip_channel_id, 'snoop',
            app='testsuite', spy='both')
        if response.status_code // 100 != 2:
            LOGGER.error("Snoop creation failed: %d %s",
                         response.status_code, response.text)
            self.test_object.set_passed(False)
            self.test_object.stop_reactor()
            return
        # Do NOT wait for Snoop's StasisStart. Schedule send immediately.
        # If Snoop's StasisStart arrives before send fires (track-all-stasis),
        # channel_id will be overwritten with Snoop ID -> 501.
        reactor.callLater(self.send_delay, self._send_initial_requests)

    def _create_snoop(self):
        self.pjsip_channel_id = self.channel_id
        response = self.ari.post(
            'channels', self.pjsip_channel_id, 'snoop',
            app='testsuite', spy='both')
        if response.status_code // 100 != 2:
            LOGGER.error("Snoop creation failed: %d %s",
                         response.status_code, response.text)
            self.test_object.set_passed(False)
            self.test_object.stop_reactor()
            return
        self.channel_id = None
        self.waiting_for_snoop = True

    def _delete_channel(self):
        target = self.pjsip_channel_id or self.channel_id
        if not target or self.channel_destroyed:
            return

        self.ari.set_allow_errors(True)
        response = self.ari.delete('channels', target)
        self.ari.set_allow_errors(False)
        if response.status_code // 100 != 2 and response.status_code != 404:
            LOGGER.error("Delete channel %s failed: %d %s",
                         target, response.status_code, response.text)
            self.test_object.set_passed(False)

    def _maybe_finish(self):
        if self._completed:
            return

        if not self._all_requests_sent():
            return

        for request in self.requests:
            if request['events_seen'] != request['event_count']:
                return

        self._completed = True
        if self.config.get('cleanup-channel', True) and not self.channel_destroyed:
            self._delete_channel()
        reactor.callLater(self.quiet_time, self.test_object.stop_reactor)

    def _all_requests_sent(self):
        return all(request['sent'] for request in self.requests)

    def _find_request(self, request_id):
        for request in self.requests:
            if request['request_id'] == request_id:
                return request
        return None

    def _is_target_channel(self, channel):
        if not channel:
            return False
        if self.channel_id:
            return channel.get('id') == self.channel_id
        if self.channel_name:
            return channel.get('name') == self.channel_name
        return True

    def _on_stop(self, *args):
        for scenario in self.scenarios:
            try:
                scenario.kill()
            except Exception:
                pass

        if self.unexpected_delivery_events:
            self.test_object.set_passed(False)

        for request in self.requests:
            if not request['sent']:
                LOGGER.error("Request %s was never sent", request['request_id'])
                self.test_object.set_passed(False)
            if not request['response_ok']:
                self.test_object.set_passed(False)
            if request['events_seen'] != request['event_count']:
                LOGGER.error(
                    "Request %s expected %d delivery events, got %d",
                    request['request_id'], request['event_count'],
                    request['events_seen'])
                self.test_object.set_passed(False)

        if self.test_object.passed is not False:
            self.test_object.set_passed(True)
