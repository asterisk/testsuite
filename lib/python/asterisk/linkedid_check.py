#!/usr/bin/env python
""" Asterisk TestSuite LinkedId Propagation Test

Copyright (C) 2014, Digium, Inc.
Scott Griepentrog <sgriepentrog@digium.com>

This program is free software, distributed under the terms
of the GNU General Public License Version 2.


This monitors bridge enter/exit and CEL events, and builds
a picture of which channels are bridged together, and when
their LinkedID changes, and then verifies that each change
is correct.

Note: The BridgeEnter and CEL 'BRIDGE_ENTER' events can be
in either order - so wait for both to arrive before making
a judgement on the LinkedID.

This test can be added to any other bridging test to add a
layer of LinkedId Propagation checking to it.  However the
creation of channels has to be done one at a time by using
a Newchannel event to trigger the next one - so that order
of creation can be determined.  Also required is that this
test module is listed before others to that it can process
bridge events first before the test makes changes.

"""

import logging

LOGGER = logging.getLogger(__name__)


class LinkedIdChannel(object):
    def __init__(self, uniqueid, order, test):
        """ This initializes the LinkedID Channel object

        Keyword Arguments:
        uniqueid    - channel unique id
        order       - creation order
        test        - the test_object used to set failure indication
        """
        self.order = order              # creation order for age test
        self.uniqueid = uniqueid        # uniqueid for channel
        self.linkedid = False           # what linkedid should be
        self.cel_linkedid = False       # linkedid from last CEL event
        self.failed = False             # squelch repeated errors
        self.test = test                # copy of test object (to set fail)

        LOGGER.info('New channel %s created order #%d' %
                    (uniqueid, self.order))

    def event(self, event):
        """ This handles a channel event

        Keyword Arguments:
        event       - key value pairs in dict from AMI CEL event
        """
        uniqueid = event['uniqueid']
        linked = event['linkedid']

        if self.cel_linkedid != linked:
            previous = self.cel_linkedid
            self.cel_linkedid = linked
            LOGGER.info('%s changed LinkedID %s to %s after CEL %s' %
                        (uniqueid, previous, linked, event['eventname']))

            # this could be a CEL BRIDGE_ENTER showing up before the
            # BridgeEnter, so don't evaluate what it should be here
            # as it will caught on the next CEL event if wrong
            return

        # check that this CEL event has the correct LinkedId
        if self.cel_linkedid != self.linkedid and not self.failed:
            LOGGER.info('%s has LinkedID %s after CEL %s ' %
                        (uniqueid, self.cel_linkedid, event['eventname']))

            """ This is not currently considered an error but should be!

            If the first channel that entered the bridge has it's linkedid
            changed when the second channel enters, there is not another CEL
            event divulging the new linkedid, and it can be an old linkedid
            pulled from the stasis cache when the next event occurs on this
            channel.

            TODO: change this to error and set failure when Asterisk fixed
            """
            LOGGER.warning('LinkedID Propagation error:  ' +
                           'Last CEL on %s has %s should be %s' %
                           (uniqueid, self.cel_linkedid, self.linkedid))

            self.failed = True
            #self.test.set_passed(False)

    def getvar_callback(self, result):
        LOGGER.info('AMI query indicates channel %s has linkedid %s' %
                    (self.uniqueid, result))

        if self.linkedid != result:
            LOGGER.error('LinkedID Propagation error:  ' +
                         'Channel %s has %s should be %s' %
                         (self.uniqueid, result, self.linkedid))
            self.test.set_passed(False)

    def getvar_failback(self, reason):
        LOGGER.error('Failed to getvar linkedid for channel %s: %s' %
                     (self.uniqueid, reason))

    def query_linkedid(self, ami):
        """ query the channel to get the current linkedid

        Keyword Arguments:
        ami     - The ami manager object
        """
        ami.getVar(self.uniqueid, 'CHANNEL(linkedid)'
                   ).addCallbacks(self.getvar_callback, self.getvar_failback)


class LinkedIdCheck(object):
    def __init__(self, module_config, test_object):
        """ This initializes the LinkedId Check test object.

        Keyword Arguments:
        module_config  - configuration section (not used)
        test_object    - the TestCase object running the test
        """
        # ask AMI to let us hook in for events
        test_object.register_ami_observer(self.ami_connect)
        # keep a ref to test_object so we can set failure
        self.test_object = test_object

        #  initialize variables used in this class
        self.channels = {}          # channel objects
        self.bridges = {}           # bridge num for readable logs
        self.chan_bridge = {}       # what bridgeid is chan in or False

    def ami_connect(self, ami):
        """ register with StarPy AMI manager to get events

        This registers with the StarPY AMI manager to get
        the events we are interested in.

        Keyword Arguments:
        ami    - The AMI manager object
        """
        ami.registerEvent('Newchannel', self.new_channel)
        ami.registerEvent('CEL', self.channel_event)
        ami.registerEvent('BridgeEnter', self.bridge_enter)
        ami.registerEvent('BridgeLeave', self.bridge_leave)

    def new_channel(self, ami, event):
        """ handle new channel events to get correct order

        It is possible for CEL CHAN_START events to arrive in
        the wrong order, which throws off age calculations.
        It is also possible for the New Channel event to be
        later than the CEL CHAN_START, so handle creation on
        either.

        Keyword Arguments:
        ami     - The AMI manager object
        event   - The event key/value pairs in a dict
        """
        uniqueid = event['uniqueid']
        if uniqueid not in self.channels.keys():
            new_chan = LinkedIdChannel(uniqueid,
                                       len(self.channels) + 1,
                                       self.test_object)
            self.channels[uniqueid] = new_chan
            self.chan_bridge[uniqueid] = False

    def channel_event(self, ami, event):
        """ handle channel events to get channel's LinkedID

        This handles Channel Event Logger events, which
        are monitored because they contain the LinkedID
        associated with the channel

        Keyword Arguments
        ami    - The AMI manager object
        event  - The event key/value pairs in a dict
        """

        # insure the channel object is created for a new uniqueid
        uniqueid = event['uniqueid']
        linkedid = event['linkedid']
        if not uniqueid in self.channels.keys():
            new_chan = LinkedIdChannel(uniqueid,
                                       len(self.channels) + 1,
                                       self.test_object)
            self.channels[uniqueid] = new_chan
            self.chan_bridge[uniqueid] = False

        # insure starting linkedid is updated
        if not self.channels[uniqueid].linkedid:
            self.channels[uniqueid].linkedid = linkedid
            self.channels[uniqueid].cel_linkedid = linkedid
            LOGGER.info('%s has LinkedID %s at %s ' %
                        (uniqueid, event['linkedid'], event['eventname']))

        # pass event to the channel
        self.channels[uniqueid].event(event)

    def bridge_enter(self, ami, event):
        """ handle bridge enter events, track bridged channels

        This handles Bridge Enter events, used to track
        which channels are in which bridges together.

        Keyword Arguments
        ami    - The AMI manager object
        event  - The event key/value pairs in a dict
        """
        uniqueid = event['uniqueid']
        bridgeid = event['bridgeuniqueid']

        # uniqueid bridges numerically in logs for better readability
        if bridgeid not in self.bridges.keys():
            self.bridges[bridgeid] = len(self.bridges) + 1

        # list of channels in this bridge
        bridged_with = [uid for uid in self.chan_bridge.keys()
                        if self.chan_bridge[uid] == bridgeid]

        LOGGER.info('%s entered bridge #%d with %s' %
                    (uniqueid, self.bridges[bridgeid], bridged_with))

        # mark this channel in the bridge
        self.chan_bridge[uniqueid] = bridgeid

        # if alone in the bridge, skip the checks
        if not bridged_with:
            return

        # determine the correct linkedid for chans in this bridge
        bridged_with.append(uniqueid)
        oldest = False
        for uid in bridged_with:
            linkedid = self.channels[uid].linkedid
            LOGGER.info('EVAL => %s has LinkedID %s (%d)' %
                        (uid, linkedid, self.channels[linkedid].order))
            if not oldest:
                oldest = self.channels[uid].linkedid
            elif self.channels[linkedid].order < self.channels[oldest].order:
                oldest = self.channels[uid].linkedid

        LOGGER.info('EVAL RESULT: oldest LinkedID in bridge #%d is %s (%d)' %
                    (self.bridges[bridgeid], oldest,
                     self.channels[oldest].order))

        # set the value that it should be for comparison later
        # when the next CEL event arrives
        for uid in bridged_with:
            self.channels[uid].linkedid = oldest

            # have each channel query the linkedid because CEL may be old
            self.channels[uid].query_linkedid(ami)

    def bridge_leave(self, ami, event):
        """ handle bridge leave events

        This handles Bridge Leave events, used to track
        which channels are in which bridges together.

        Keyword Arguments
        ami    - The AMI manager object
        event  - The event key/value pairs in a dict
        """
        uniqueid = event['uniqueid']
        bridgeid = event['bridgeuniqueid']
        self.chan_bridge[uniqueid] = False
        bridged_with = [uid for uid in self.chan_bridge.keys()
                        if self.chan_bridge[uid] == bridgeid]
        LOGGER.info('%s left bridge #%d leaving %s' %
                    (uniqueid, self.bridges[bridgeid], bridged_with))

# vim:sw=4:ts=4:expandtab:textwidth=79
