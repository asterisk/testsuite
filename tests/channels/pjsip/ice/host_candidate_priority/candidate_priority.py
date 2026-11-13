"""Regression coverage for ASTDEV-1181.

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
"""

import logging
import os
import re

from asterisk.sipp import SIPpScenario
from asterisk.test_case import TestCase
from asterisk.test_suite_utils import get_bindable_ipv4_addr


LOGGER = logging.getLogger(__name__)
MAPPED_ADDRESS = '192.0.2.1'


class CandidatePriorityTest(TestCase):
    """Inspect actual SDP without depending on ICE nomination or NAT access."""

    def __init__(self, test_path, test_config):
        super().__init__(test_path, test_config=test_config)
        self.create_asterisk()
        self.local_address = get_bindable_ipv4_addr()
        if not self.local_address or self.local_address == MAPPED_ADDRESS:
            raise ValueError('A non-loopback IPv4 address distinct from the mapping is required')

        self.cases = ('include_local', 'mapped_only', 'duplicate', 'replacement', 'unmapped')
        self.case_index = 0
        self.configure_case()

    def configure_case(self):
        """Install the next mapping and ACLs before creating a new RTP instance."""
        case = self.cases[self.case_index]
        mapped_address = self.local_address if case == 'duplicate' else MAPPED_ADDRESS
        config_text = '[general]\nicesupport=yes\n'
        if case != 'include_local':
            # Isolate one address, including the case where the actual local
            # address is denied but its additional mapping is still allowed.
            allowed = (mapped_address if case in ('mapped_only', 'replacement')
                       else self.local_address)
            config_text += ('ice_deny=0.0.0.0/0\nice_deny=::/0\n'
                            'ice_permit={}/32\n'.format(allowed))
        if case != 'unmapped':
            include = '' if case == 'replacement' else ',include_local_address'
            config_text += '[ice_host_candidates]\n{} => {}{}\n'.format(
                self.local_address, mapped_address, include)
        with open(self.ast[0].get_path('astetcdir', 'rtp.conf'), 'w') as config:
            config.write(config_text)

        self.message_file = os.path.join(self.testlogdir, '{}-messages.log'.format(case))
        self.scenario = SIPpScenario(self.test_name, {
            'scenario': 'invite.xml',
            '-message_file': self.message_file,
        }, positional_args=('-trace_msg',))

    def run(self):
        super().run()
        self.start_scenario()

    def start_scenario(self, result=None):
        LOGGER.info('Running ICE priority case: %s', self.cases[self.case_index])
        self.scenario.run(self).addCallback(self.scenario_complete)

    def scenario_complete(self, scenario):
        """Validate each SDP answer in the completed SIPp message trace."""
        try:
            if not scenario.passed:
                raise ValueError('SIPp scenario failed')
            with open(self.message_file) as messages:
                trace = messages.read()
            answers = 0
            for response in re.finditer(r'^SIP/2\.0 200 [^\n]*\n', trace, re.M):
                headers, body = trace[response.end():].split('\n\n', 1)
                length = int(re.search(r'Content-Length:\s*(\d+)', headers, re.I)[1])
                body = body[:length]
                if body.startswith('v=0'):
                    answers += 1
                    self.check_candidates(body)
            if not answers:
                raise ValueError('No SDP answer found in SIPp trace')
        except (OSError, ValueError, AssertionError) as error:
            LOGGER.error('ICE candidate validation failed: %s', error)
            self.set_passed(False)
            self.stop_reactor()
            return scenario

        self.case_index += 1
        if self.case_index == len(self.cases):
            self.set_passed(True)
            self.stop_reactor()
        else:
            self.configure_case()
            self.ast[0].cli_exec('module reload res_rtp_asterisk.so').addCallbacks(
                self.start_scenario, self.reload_failed)
        return scenario

    def reload_failed(self, failure):
        LOGGER.error('Could not reload RTP configuration: %s', failure)
        self.set_passed(False)
        self.stop_reactor()

    def check_candidates(self, sdp):
        """Check uniqueness, local-over-mapped ordering, and sole-address preference."""
        case = self.cases[self.case_index]
        candidates = re.findall(
            r'^a=candidate:\S+ (\d+) UDP (\d+) (\S+) \d+ typ host\b',
            sdp, re.M | re.I)
        for component in ('1', '2'):
            host_candidates = [(address, int(priority))
                               for comp, priority, address in candidates
                               if comp == component]
            priorities = dict(host_candidates)
            LOGGER.info('%s component %s host priorities: %s', case, component, priorities)
            assert len({priority for _, priority in host_candidates}) == len(host_candidates), (
                'Component {} has duplicate host priorities: {}'.format(component, host_candidates))
            if case == 'include_local':
                assert {self.local_address, MAPPED_ADDRESS} <= set(priorities), (
                    'Component {} is missing local or mapped candidates: {}'.format(
                        component, priorities))
                assert priorities[self.local_address] > priorities[MAPPED_ADDRESS], (
                    'Component {} must prefer the local address: {}'.format(component, priorities))
            else:
                expected = (MAPPED_ADDRESS if case in ('mapped_only', 'replacement')
                            else self.local_address)
                assert len(host_candidates) == 1 and expected in priorities, (
                    '{} component {} must have only {}: {}'.format(
                        case, component, expected, host_candidates))
                assert ((priorities[expected] >> 8) & 0xffff) == 65535, (
                    '{} component {} must use local preference 65535: {}'.format(
                        case, component, priorities))
