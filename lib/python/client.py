#! /usr/bin/env python

from twisted.application import service, internet
from twisted.internet import reactor
from starpy import manager, fastagi, utilapplication, menu
import os, logging, pprint, time, sys, threading

sys.path.append("lib/python")
from asterisk.asterisk import Asterisk

"""
This module is meant to be instantiated with the following parameters:
def __init__(self, myargv, myasterisk, mytester, mytimeout = 5)
myargv - the arguments passed to main
myasterisk - the Asterisk instance created from the Asterisk class
mytester - an instance of the created test class
mytimeout - (optional) number of seconds before a test is considered to have
timed out

The mytester param gives the watcher class the necessary information to call
each test method. Each test method is defined in a class of your choosing
similar to below. The purpose of each test method is to set the events to be
monitored for as well as optionally events to send which also need events
monitored.

    def test0(self, watcher):
        event1 = [{'response' : 'Success', 'ping' : 'Pong'}]
        watcher.add_event(event1)
        event_send = {'Action' : 'ping'}
        watcher.add_send_event(event_send)

    # identical test
    def test1(self, watcher):
        event1 = [{'response' : 'Success', 'ping' : 'Pong'}]
        watcher.add_event(event1)
        event_send = {'Action' : 'ping'}
        watcher.add_send_event(event_send)

    def test2(self, watcher):
        event1 = [{'event' : 'Alarm', 'channel' : '17' }]
        event2 = [{'event' : 'Alarm', 'channel' : '18' }]
        event3 = [{'event' : 'Alarm', 'channel' : '20' }, {'event' : 'Alarm', 'channel' : '19'}]
        watcher.add_event(event1)
        watcher.add_event(event2)
        watcher.add_event(event3)
        watcher.set_ordered(True)

        # alternative event set up:
        #watcher.set_events(False,
        #   [[{'event' : 'Alarm', 'channel' : '18' }],
        #   [{'event' : 'Alarm', 'channel' : '17' }],
        #   [{'event' : 'Alarm', 'channel' : '19' }, {'event' : 'Alarm', 'channel' : '20'}]])

Events are described using dictionaries very similar to how they would appear
in a manager session. Only the portion of the event you want to match should
be specified.

Events to monitor are added via add_event. Add_event takes a list of
dictionaries. The reason it is a list is to cover the case where you want to
specify either event may be considered as a successful match.

Events to send are added via add_send_event. Add_send_event takes a dictionary
representing the event to send.

The client module contains a set_ordered method which may either be set True or
False, depending on whether or not the order of the event matching matters. Or
the  set_events method may be used which the first argument sets the ordering
method and the second argument is a list of list of dictionaries for all events
to be matched.

These are the supported event monitoring scenarios:

S1: unordered
[SEND] -> 3 -> 1 -> 2

S2: ordered
[SEND] -> 1 -> 2 -> 3

S3: optional events
[SEND] -> 1 -> {2, 3} -> 4

The [SEND] above is optional and corresponds to the add_send_event method,
which also takes a dictionary representing the event to be sent.

"""



class EventWatcher():

    def start_asterisk(self):
        self.log.info("Starting Asterisk")
        self.asterisk.start()
        self.asterisk.cli_exec("core set verbose 10")
        self.asterisk.cli_exec("core set debug 3")

    def stop_asterisk(self):
        if not self.standalone:
            self.asterisk.stop()

    def clear_vars(self):

        self.event_list = list()
        self.count = 0
        self.send_event_list = list()
        self.ordered = False

    def __init__(self, myargv, myasterisk, mytester, mytimeout = 5):
        self.log = logging.getLogger('TestAMI')
        self.log.setLevel(logging.INFO)
        self.ami = None
        self.testcount = 0
        self.passed = True
        self.call_id = None
        self.working_dir = os.path.dirname(myargv[0])
        self.testobj = mytester
        self.timeout_sec = mytimeout

        if len(myargv) == 1:
            self.standalone = True
        else:
            self.standalone = False
            if myasterisk == None:
                self.passed = False
                self.log.critical("Fail to pass Asterisk instance!")
                return

            self.asterisk = myasterisk

        self.reactor_lock = threading.Lock()
        self.reactor_stopped = False

        self.clear_vars()

        if self.standalone:
            return

        self.start_asterisk()

    def set_ordered(self, ordered):
        self.ordered = ordered

    def add_event(self, event):
        self.event_list.append(event)
        self.count = self.count + 1

    def add_send_event(self, event):
        self.send_event_list.append(event)

    def set_events(self, ordered, list):
        self.event_list = list
        self.count = len(list)
        self.ordered = ordered

    def show_events(self):
        if self.log.getEffectiveLevel() < logging.DEBUG:
            return

        self.log.debug("Showing events")
        for n in self.event_list:
            self.log.debug("Event: %s" % n)

    def get_events(self):
        return self.event_list

    def check_events(self):
        if not self.event_list:
            return False

        for events in self.event_list:
            matched = False
            for event in events:
                if "match" in event:
                    matched = True
                    continue
            if not matched:
                return False
        return True

    def timeout(self):
        self.log.debug("Timed out")
        self.passed = False
        self.reactor_lock.acquire()
        if not self.reactor_stopped:
            reactor.stop()
            self.reactor_stopped = True
            self.stop_asterisk()
        self.reactor_lock.release()

    def end_test(self):
        self.reactor_lock.acquire()
        if not self.reactor_stopped:
            self.call_id.cancel()
            reactor.stop()
            self.reactor_stopped = True
            self.stop_asterisk()
        self.reactor_lock.release()
        self.log.info("DONE - end_test")

    def dict_in_dict(self, d_set, d_subset):
        return len(d_subset) == len(set(d_subset.items()) & set(d_set.items()))

    def start(self):
        utilapplication.UtilApplication.configFiles = (os.getcwd() + '/' + self.working_dir + '/starpy.conf', 'starpy.conf')
        # Log into AMI
        amiDF = utilapplication.UtilApplication().amiSpecifier.login().addCallbacks(self.on_connect, self.on_failure)

    def send_events(self, ami):
        if self.send_event_list:
            for amessage in self.send_event_list:
                id = ami.sendMessage(amessage, self.on_sent_response)
                self.log.debug("Sending %s with id %s" % (amessage, id))

    def on_failure(self, ami):
        self.log.critical("Stopping asterisk, login failure")
        self.passed = False
        self.stop_asterisk()

    def on_connect(self, ami):
        """Register for AMI events"""
        # XXX should handle asterisk reboots (at the moment the AMI 
        # interface will just stop generating events), not a practical
        # problem at the moment, but should have a periodic check to be sure
        # the interface is still up, and if not, should close and restart
        ami.status().addCallback(self.on_status, ami=ami)

        if len(self.event_list) or len(self.send_event_list) != 0:
            self.log.warn("Don't load events outside of a test method!")

        self.load_next_test(ami, True)

        if len(self.event_list) == 0:
            self.log.error("No events to monitor!")

        ami.registerEvent(None, self.on_any_event)

        self.ami = ami
        self.send_events(ami)

    def on_sent_response(self, result):
        # don't care about connection terminated event
        if result.__str__() != "Connection was closed cleanly: FastAGI connection terminated.":
            self.log.debug("Result from sent event: %s", result)
            self.on_any_event(self.ami, result)
        else:
            self.log.debug("Ignoring connection close event")

    def connectionLost(reason):
        self.log.critical("Connection lost: %s", reason)

    def on_any_event(self, ami, event):

        self.log.debug("Running on_any_event")

        if not self.ordered:
            for next_events in self.event_list:
                for next_event in next_events:
                    self.log.debug("Looking at %s vs %s" % (next_event, event))
                    if self.dict_in_dict(event, next_event):
                        next_event.update({"match": time.time()})
                        self.log.debug("New event %s" % next_event)
                        self.count = self.count - 1
                        if self.count == 0:
                            self.load_next_test(ami)
        else:
            index = abs(self.count - len(self.event_list))
            for next_event in self.event_list[index]:
                if self.dict_in_dict(event, next_event):
                    next_event.update({"match": time.time()})
                    self.log.debug("New event %s" % next_event)
                    self.count = self.count - 1
                    if self.count == 0:
                        self.load_next_test(ami)
                    continue

    def exec_next_test(self, count, toexec):
        self.log.info("Next test count %s", count)

        if not hasattr(self.testobj, toexec):
             self.log.debug("No more tests")
             return -1

        self.log.debug("Test method %s exists", toexec)
        if self.call_id:
            self.call_id.cancel()
        method = getattr(self.testobj, toexec)
        self.log.debug("Begin executing %s", toexec)
        method(self)
        self.log.debug("Finish executing %s", toexec)
        if len(self.event_list) > 0:
            self.log.debug("Rescheduling timeout")
            self.call_id = reactor.callLater(self.timeout_sec, self.timeout)
            return 0

        self.log.warn("Returning, no events added by test method!")
        return -1 # exception or something

    def load_next_test(self, ami, firstrun=None):
        if not firstrun:
            self.log.debug("About to shut down all monitoring")
            ami.deregisterEvent(None, None)

            passed = self.check_events()
            if not passed:
                self.log.debug("TEST FAILED")
                self.passed = False
                self.end_test()
                return

            self.log.debug("Test passed")
            self.show_events()
            self.clear_vars()

        toexec = "test" + str(self.testcount)
        res = self.exec_next_test(self.testcount, toexec)
        self.log.debug("res %s from exec %s" % (res, toexec))
        if res == -1:
            self.ami = None
            self.end_test()
            return
        self.testcount = self.testcount + 1
        ami.registerEvent(None, self.on_any_event)
        self.send_events(ami)

    def on_status(self, events, ami=None):
        self.log.debug("Initial channel status retrieved")
        if events:
            self.log.critical("Test expects no channels to have started yet, aborting!")
            ami.deregisterEvent(None, None)
            self.passed = False
            self.end_test()
            for event in events:
                self.log.debug("Received event: %s", event)

if __name__ == "__main__":
    print "This code is meant to be imported"

# vim:sw=4:ts=4:expandtab:textwidth=79
