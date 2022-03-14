'''
Copyright (C) 2022, Sangoma Technologies Corp
Mike Bradeen <mbradeen@sangoma.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.

The extension_bank is a set of helper call backs that let us kick off sipp
scenarios from within our pluggable test events.

These call backs are wrappers that let us map out specific scenarios to a
set of pre-defined scenario invocation patterns. Pick a matching pattern
from the pattern_* functions then either use one of the mapping functions
at the bottom (ie alice_calls) or write your own in order to use sipp
scenarios at specific points in your test. Make sure that your tests's sipp
directory has a matching scenario file so you can invoke it using one of
the mapping functions.

For example, to invoke your test's sipp/alice_calls.xml on port 5161 upon a
StasisStart ari event, you might do something like:
        ari-events:
            match:
                type: StasisStart
                application: testsuite
                args: []
                channel:
                    name: 'Local/s@default-.*'
            count: 1
        callback:
            module: extension_bank
            method: alice_calls

We try to assume alice, bob and charlie are local and live on 5161, 5162 and
5163 respectively.  If we need more than one, +10 for each instance.

'''

import logging
from sys import path

from asterisk.sipp import SIPpScenario

LOGGER = logging.getLogger(__name__)

# Scenario invocation patterns.  Add more as needed.
def pattern_simple_scenario(test_object, scenario, port, target_host='127.0.0.1', delay="0"):

    sipp_pattern = SIPpScenario(test_object.test_name,
                                {'scenario': scenario,
                                 '-p': port,
                                 '-sleep': delay},
                                target=target_host)

    sipp_pattern.run(test_object)

    return True

def pattern_repeating_scenario(test_object, scenario, port, target_host='127.0.0.1', delay="0", calls="1"):

    sipp_pattern = SIPpScenario(test_object.test_name,
                                {'scenario': scenario,
                                 '-p': port,
                                 '-sleep': delay,
                                 '-m': calls,
                                 '-l': calls},
                                target=target_host)

    sipp_pattern.run(test_object)

    return True

def pattern_ooscf_scenario(test_object, scenario, port, oocsf_file, target_host='127.0.0.1', delay="0"):

    sipp_pattern = SIPpScenario(test_object.test_name,
                                {'scenario': scenario,
                                 '-p': port,
                                 '-oocsf' : oocsf_file,
                                 '-sleep': delay},
                                target=target_host)

    sipp_pattern.run(test_object)

    return True

def pattern_attended_transfer(test_object, referer_scenario, referer_port,
                                            referee_scenario, referee_port, delay = 3):

    def _start_referer_scenario(referer, test_object):
        referer.run(test_object)

    sipp_referer = SIPpScenario(test_object.test_name,
                                {'scenario': referer_scenario,
                                 '-p': referer_port,
                                 '-3pcc': '127.0.0.1:5064'},
                                target='127.0.0.1')
    sipp_referee = SIPpScenario(test_object.test_name,
                                {'scenario': referee_scenario,
                                 '-p': referee_port,
                                 '-3pcc': '127.0.0.1:5064'},
                                target='127.0.0.1')

    sipp_referee.run(test_object)

    # The 3pcc scenario that first uses sendCmd (sipp_referer) will establish
    # a TCP socket with the other scenario (sipp_referee). This _must_ start
    # after sipp_referee - give it a few seconds to get the process off the
    # ground.
    from twisted.internet import reactor
    reactor.callLater(delay, _start_referer_scenario, sipp_referer, test_object)

    return True

# Define local callbacks that use the above scenario invoker patterns
# If you want to use one of the scenarios referenced below, it needs to be
# defined in your test's sipp directory.  All this does is map a call back to
# a scenario file, you must also provide that file!
# While the samples at the bottom cover a good number of cases, but if you need
# more, create a local module that defines them unless they are universal
# enough to go here

# alice, bob and charlie make a call.  Who do they call?
def alice_calls(test_object, triggered_by=None, ari=None, event=None):
    LOGGER.debug("alice_calls(%r)" % event)
    return pattern_simple_scenario(test_object, "alice-calls.xml", "5161")

def bob_calls(test_object, triggered_by=None, ari=None, event=None):
    LOGGER.debug("bob_calls(%r)" % event)
    return pattern_simple_scenario(test_object, "bob-calls.xml", "5162")

def charlie_calls(test_object, triggered_by=None, ari=None, event=None):
    LOGGER.debug("charlie_calls(%r)" % event)
    return pattern_simple_scenario(test_object, "charlie-calls.xml", "5163")

# alice, bob and charlie register.
def alice_registers(test_object, triggered_by=None, ari=None, event=None):
    LOGGER.debug("alice_registers(%r)" % event)
    return pattern_simple_scenario(test_object, "alice-registers.xml", "5161")

def bob_registers(test_object, triggered_by=None, ari=None, event=None):
    LOGGER.debug("bob_registers(%r)" % event)
    return pattern_simple_scenario(test_object, "bob-registers.xml", "5162")

def charlie_registers(test_object, triggered_by=None, ari=None, event=None):
    LOGGER.debug("charlie_registers(%r)" % event)
    return pattern_simple_scenario(test_object, "charlie-registers.xml", "5163")

# alice, bob and charlie wait for a call
def alice_waits(test_object, triggered_by=None, ari=None, event=None):
    LOGGER.debug("alice_waits(%r)" % event)
    return pattern_simple_scenario(test_object, "wait-for-a-call.xml", "5161")

def bob_waits(test_object, triggered_by=None, ari=None, event=None):
    LOGGER.debug("bob_waits(%r)" % event)
    return pattern_simple_scenario(test_object, "wait-for-a-call.xml", "5162")

def charlie_waits(test_object, triggered_by=None, ari=None, event=None):
    LOGGER.debug("charlie_waits(%r)" % event)
    return pattern_simple_scenario(test_object, "wait-for-a-call.xml", "5163")

# alice, bob and charlie register then wait for a call
def alice_registers_then_waits(test_object, triggered_by=None, ari=None, event=None):
    LOGGER.debug("alice_registers_then_waits(%r)" % event)
    return pattern_ooscf_scenario(test_object, "alice-registers.xml", "5161", "wait-for-a-call.xml")

def bob_registers_then_waits(test_object, triggered_by=None, ari=None, event=None):
    LOGGER.debug("bob_registers_then_waits(%r)" % event)
    return pattern_ooscf_scenario(test_object, "bob-registers.xml", "5162", "wait-for-a-call.xml")

def charlie_registers_then_waits(test_object, triggered_by=None, ari=None, event=None):
    LOGGER.debug("charlie_registers_then_waits(%r)" % event)
    return pattern_ooscf_scenario(test_object, "charlie-registers.xml", "5163", "wait-for-a-call.xml")

# default attended transfer 3pcc scenario
def default_attended_transfer(test_object, triggered_by=None, ari=None, event=None):
    LOGGER.debug("default_attended_transfer(%r)" % event)
    return pattern_attended_transfer(test_object, "referer.xml", "5161", "referee.xml", "5171", 1)

# example double-scenarios
def bob_waits_while_alice_calls(test_object, triggered_by=None, ari=None, event=None):
    LOGGER.debug("bob_waits_while_alice_calls(%r)" % event)
    pattern_simple_scenario(test_object, "wait-for-a-call.xml", "5162")
    pattern_attended_transfer(test_object, "referer.xml", "5161", "referee.xml", "5171", 1)
    return True

def alice_and_bob_call(test_object, triggered_by=None, ari=None, event=None):
    LOGGER.debug("alice_and_bob_call(%r)" % event)
    pattern_simple_scenario(test_object, "alice-calls.xml", "5161")
    pattern_simple_scenario(test_object, "bob-calls.xml", "5162")
    return True

# let bob and charlie wait while alice does a transfer
def bob_and_charlie_wait_while_alice_calls(test_object, triggered_by=None, ari=None, event=None):
    LOGGER.debug("bob_and_charlie_wait_while_alice_calls(%r)" % event)
    pattern_simple_scenario(test_object, "wait-for-a-call.xml", "5162")
    pattern_simple_scenario(test_object, "wait-for-a-call.xml", "5163")
    pattern_attended_transfer(test_object, "referer.xml", "5161", "referee.xml", "5171", 1)
    return True

# let bob and charlie wait while alice does a transfer
def bob_and_charlie_regwait_while_alice_calls(test_object, triggered_by=None, ari=None, event=None):
    LOGGER.debug("bob_and_charlie_wait_while_alice_calls(%r)" % event)
    pattern_ooscf_scenario(test_object, "bob-registers.xml", "5162", "wait-for-a-call.xml")
    pattern_ooscf_scenario(test_object, "charlie-registers.xml", "5163", "wait-for-a-call.xml")
    pattern_attended_transfer(test_object, "referer.xml", "5161", "referee.xml", "5171", 3)
    return True

# wait for twelve calls
def alice_waits_twelve(test_object, triggered_by=None, ari=None, event=None):
    LOGGER.debug("alice_waits twelve(%r)" % event)
    return pattern_repeating_scenario(test_object, "wait-for-a-call.xml", "5161", calls="12")
