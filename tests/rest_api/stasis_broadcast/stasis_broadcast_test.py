"""
Stasis broadcast test callbacks

Tests that channels can be broadcast to multiple ARI applications
and that first-claim-wins semantics work correctly.
"""

import logging

LOGGER = logging.getLogger(__name__)

channel_id = None
broadcast_received = False
claim_received = False
trigger_channel_id = None


def on_trigger_start(ari, event, test_object):
    """Handle the initial trigger channel entering Stasis - start the test"""
    global trigger_channel_id
    
    LOGGER.info("Trigger channel entered Stasis: %s" % event)
    trigger_channel_id = event['channel']['id']
    
    # Originate the channel that will be broadcast via AMI
    LOGGER.info("Originating broadcast channel via AMI")
    ami = test_object.ami[0]
    ami.originate(
        channel='Local/broadcast@default',
        application='Echo',
        timeout=30000
    ).addErrback(test_object.handle_originate_failure)
    
    # Don't delete the trigger channel yet - keep it alive until broadcast completes
    
    return True


def on_broadcast(ari, event, test_object):
    """Handle CallBroadcast event"""
    global channel_id, broadcast_received
    
    LOGGER.info("CallBroadcast received for app %s: %s" % (event['application'], event))
    broadcast_received = True
    channel_id = event['channel']['id']
    
    # Each app that receives the broadcast tries to claim - first one wins
    LOGGER.info("Attempting to claim channel %s for application %s" % (channel_id, event['application']))
    try:
        ari.post('events/claim', channelId=channel_id, application=event['application'])
        LOGGER.info("Claim succeeded for %s" % event['application'])
    except Exception as e:
        # 404 or 409 is expected if another app claimed first - this is normal!
        LOGGER.info("Claim failed for %s (expected if another app won): %s" % (event['application'], e))
    
    return True


def on_claimed(ari, event, test_object):
    """Handle CallClaimed event"""
    global claim_received
    
    LOGGER.info("CallClaimed received: %s" % event)
    claim_received = True
    
    return True


def on_start(ari, event, test_object):
    """Handle StasisStart event - channel entered Stasis after being claimed"""
    global channel_id, claim_received, broadcast_received, trigger_channel_id
    
    LOGGER.info("StasisStart received: %s" % event)
    channel_id = event['channel']['id']
    
    # Test passes when we get StasisStart after broadcast and claim
    if broadcast_received and claim_received:
        LOGGER.info("SUCCESS: Channel entered Stasis after being claimed")
        # Delete both the broadcast channel and the trigger channel
        try:
            ari.delete('channels', channel_id)
        except Exception as e:
            LOGGER.info("Broadcast channel delete failed (may have already hung up): %s" % e)
        try:
            if trigger_channel_id:
                ari.delete('channels', trigger_channel_id)
        except Exception as e:
            LOGGER.info("Trigger channel delete failed (may have already hung up): %s" % e)
        test_object.set_passed(True)
        test_object.stop_reactor()
    else:
        LOGGER.error("StasisStart received but broadcast/claim not complete")
        test_object.set_passed(False)
        test_object.stop_reactor()
    
    return True
