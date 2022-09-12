'''
Copyright (C) 2022, Sangoma Technologies Corp
Mike Bradeen <mbradeen@sangoma.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.

The scenario_iterator is designed to let us start sipp, then perform an ami
action as a cycle of start sipp->generate event(s)->sipp stops, start sipp...
This is for tests that are performing the same test different ways or performing
different iterations of the same test.

An example would be to start a scenario that waits for a NOTIFY, then send the AMI
to generate that NOTIFY, then starts a second scenario, send a second AMI, etc.

There are two classes for this, the singleIterator and the multiIterator.  The
singleIterator is one-to-one, with each scenario start triggering the next ami and the
scenario stop triggering the next scenario start.  It is fed a pair of lists, one is a
list of scenarios and the other is a list of AMI actions.  After the final scenario,
we add a 'done' indicator to the sipp side and a final event on the AMI side, example:

scenarios = [
    {'Name': 'none'},
    {'Name': 'alice-is-notified-1.xml', 'port': '5061', 'target': '127.0.0.1'},
    {'Name': 'alice-is-notified-2.xml', 'port': '5061', 'target': '127.0.0.1'},
    {'Name': 'done'}
]

actions = [
    {'Action': 'UserEvent', 'UserEvent': 'testStarted'}
    {'Action': 'MWIUpdate', 'Mailbox': 'alice', 'NewMessages':'2', 'OldMessages':'0'},
    {'Action': 'MWIDelete', 'Mailbox': 'alice'},
    {'Action': 'UserEvent', 'UserEvent': 'testComplete'}
]

You then define a local instance and run it:

def start_test(test_object, junk):
    testrunner = singleIterator(test_object, scenarios, actions)
    testrunner.run(junk)

The multiIterator is a many-to-many mapper that allows multiple scenarios to be started, followed
by multiple actions.  The end of the last scenario in the list causes the next scenario to start.

Multiple sequences can be tied to individual actions, or vice versa. In this example we start two
scenarios but then only generate one corresponding AMI:

scenarios = [
        {'Name': 'mailbox_a', 'sequence': [
            {'Name': 'alice-is-notified-1.xml', 'port': '5061', 'target': '127.0.0.1'},
            {'Name': 'bob-is-notified-1.xml', 'port': '5062', 'target': '127.0.0.1'} ]},
        {'Name': 'done'}
]

actions = [
        {'Messages': [{'Action': 'MWIUpdate', 'Mailbox': 'mailbox_a', 'NewMessages':'2', 'OldMessages':'1'}]},
        {'Messages': [{'Action': 'UserEvent', 'UserEvent': 'testComplete'}]}
]

In the above examples, we end the test with a testComplete event that we then use to trigger the
test stop event in the corresponding yaml file, example:
ami-config:
    -
        ami-events:
            conditions:
                match:
                    Event: 'UserEvent'
                    UserEvent: 'testComplete'
            count: 1
        stop_test:

Also, this test REQUIRES the following be set in the sipp configuration section of your yaml file if
you are using a sipp scenario (like a REGISTER) to kick off the sequnce:
    stop-after-scenarios: False

A Name of 'none' for a scenario(list) or an Action of 'none' skips that particular scenario or action,
but not the other. This is mostly to allow one or more AMI events to be triggered before the
corresponding sipp scenario is started but could also allow for intermediate sipp scenarios. Setting
both to 'none' would be functionally the same as waiting for 1 second before going on to the next
iteration.

'''
from asterisk.sipp import SIPpScenarioSequence
from asterisk.sipp import SIPpScenario
from twisted.internet import reactor
import sys
import logging

sys.path.append("lib/python")

LOGGER = logging.getLogger(__name__)

sipp_terminator = {'Name': 'done'}
empty_action = {'Action': 'none'}
empty_action_list = {'Messages': [{'Action': 'none'}] }

class singleIterator(object):

    def __init__(self, test_object, scenarios, actions):
        self.test_object = test_object
        self.scenarios = scenarios
        self.actions = actions
        self.iteration = 0

    def __iterate(self):
        try:
            scenario = self.scenarios[self.iteration]
        except IndexError:
            LOGGER.warning("End of scenario list without proper termination")
            scenario = sipp_terminator
        try:
            message = self.actions[self.iteration]
        except IndexError:
            LOGGER.warning("End of action list without proper termination")
            message = empty_action

        self.iteration += 1
        if scenario['Name'] == 'none':
            # skip ahead to the next iteration but send the AMI
            # action if set. Speed up the iteration.
            self.__sendMessage(message, 0)
            reactor.callLater(1, self.run)
        elif scenario['Name'] != 'done':
            # A scenaro was specified so run it then schedule the
            # AMI event if there is one.
            self.__startScenario(scenario)
            self.__sendMessage(message)
        else:
            # At the final iteration, send any final AMI immediately
            self.__sendMessage(message, 0)

    def __startScenario(self, scenario):
        LOGGER.info("Starting sipp scenario %s" % scenario['Name'])
        sipp_scenario = SIPpScenario(self.test_object.test_name,
                                     {'scenario': scenario['Name'],
                                      '-p': scenario['port']},
                                     target=scenario['target'])
        exiter = sipp_scenario.run(self.test_object)
        exiter.addCallback(self.run)

    def __sendMessage(self, message, delay=2):
        if message['Action'] != 'none':
            testami = self.test_object.ami[0]
            LOGGER.info("Scheduling AMI %s" % message['Action'])
            reactor.callLater(delay, testami.sendMessage, message)

    def run(self, junk=None):
        self.__iterate()


class multiIterator(object):

    def __init__(self, test_object, scenariosequences, actions):
        self.test_object = test_object
        self.scenariosequences = scenariosequences
        self.actions = actions
        self.iteration = 0
        self.sequencecounter = 1

    def __iterate(self):
        try:
            sippsequence = self.scenariosequences[self.iteration]
        except IndexError:
            LOGGER.warning("End of scenarios list without proper termination")
            sippsequence = sipp_terminator
        try:
            messagesequence = self.actions[self.iteration]
        except IndexError:
            LOGGER.warning("End of action list without proper termination")
            messagesequence = empty_action_list

        self.iteration += 1
        if sippsequence['Name'] == 'none':
            # skip ahead to the next iteration but send any AMI actions if
            # set, one second apart. Run the next iteration based on how far
            # out we've scheduled messages.
            sequencedelay = self.__sendMessages(messagesequence['Messages'], 1)
            reactor.callLater(sequencedelay, self.run)
        elif sippsequence['Name'] != 'done':
            # A scenaro sequence was specified so run it then schedule the
            # AMI event(s) normally. Set the delay equal to how many scenarios
            # were registered (as seconds) to try and scale against complexity
            LOGGER.info("Starting sipp sequence %s" % sippsequence['Name'])
            self.__startScenarios(sippsequence['sequence'])
            self.__sendMessages(messagesequence['Messages'], self.sequencecounter)
        else:
            # At the final iteration, send any final AMI
            sequencedelay = self.__sendMessages(messagesequence['Messages'], 0)

    def __startScenarios(self, sippscenarios):

        sipp_sequence = SIPpScenarioSequence(self.test_object,
                                             fail_on_any=True,
                                             stop_on_done=False)
        self.sequencecounter = 0
        for scenario in sippscenarios:
            LOGGER.info("Adding scenario %s to sequence" % scenario['Name'])
            sipp_scenario = SIPpScenario(self.test_object.test_name,
                                         {'scenario': scenario['Name'],
                                          '-p': scenario['port']},
                                         target=scenario['target'])
            sipp_sequence.register_scenario(sipp_scenario)
            # keep track of how many scenarios we register so we don't
            # iterate until we have stop_callback hits for all of them
            self.sequencecounter += 1

        sipp_sequence.register_scenario_stop_callback(self.run)
        sipp_sequence.execute()

    def __sendMessages(self, messages, delay = 2):
        testami = self.test_object.ami[0]
        messagedelay = delay
        for message in messages:
            if message['Action'] !='none':
                LOGGER.info("Scheduling AMI %s" % message['Action'])
                reactor.callLater(delay, testami.sendMessage, message)
                # spread out the messages by 2 seconds
                messagedelay += 2
        # return last action's delay + 2, ie when to run the next
        # command if you want it evenly distributed and after the
        # last message scheduled here
        return messagedelay

    def run(self, junk=None):
        # only run the next iteration once there is a call-back for
        # each sipp scenario in the sequence.  Otherwise, decrement
        # until we get there
        if self.sequencecounter == 1:
            self.__iterate()
        else:
            self.sequencecounter -= 1
