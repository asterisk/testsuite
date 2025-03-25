"""
Copyright (C) 2014, Digium, Inc.
Ashley Sanders <asanders@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
"""

import logging
import requests
import uuid

LOGGER = logging.getLogger(__name__)


class BridgeInfo(object):
    """Lightweight helper class for storing bridge information."""

    def __init__(self, name='', bridge_type=''):
        """Constructor.

        Keyword Arguments:
        name          --  The name of the bridge (optional)
        bridge_type   --  The type of bridge (optional)
        """

        self.name = name
        self.bridge_type = bridge_type
        self.uid = str(uuid.uuid4())


class BridgeErrorTest(object):
    """Responsible for testing error conditions during bridge creation."""

    DEFAULT_TEST_NAME = "acme"

    DEFAULT_TEST_TYPE = "proxy_media"

    def __init__(self, ari, event):
        """Constructor.

        Keyword Arguments:
        ari     --  The wrapper object for ARI
        event   --  The ARI StasisStart event object
        """

        # The pass/fail state variable for this test.
        # Note: Value is only set to 'True' during initialization.
        self.passing = True

        # Initialize the baseline bridge info objects used during the tests
        self.baseline_bridges = [BridgeInfo('road-runner'),
                                 BridgeInfo(),
                                 BridgeInfo('wiley-coyote', 'holding'),
                                 BridgeInfo('', 'mixing')]

        # The channel id that stasis gives us in the event argument
        # Needed later for tearing down the test
        self.stasis_channel_id = event['channel']['id'] or None

        # Record state of ari.allow_errors so that it can
        # correctly be reset at the end of the test
        self.__set_ari_allow_errors = ari.allow_errors or False

    def run_test(self, ari):
        """Runs the test.

        Tries to set up the state needed by the test and running the test
        against all baseline bridges created during setup. Then tears
        down the state created during setup.

        Keyword Arguments:
        ari   --  The wrapper object for ARI
        """

        try:
            self.__setup_test(ari)
            for i in range(len(self.baseline_bridges)):
                self.__create_duplicate_bridges(ari, self.baseline_bridges[i])
        finally:
            self.__tear_down_test(ari)
        return self.passing

    def __setup_test(self, ari):
        """Sets up the state needed for the test to execute.

        Configures ARI to run the test and builds two baseline bridges to use
        during the test.

        Keyword Arguments:
        ari   --  The wrapper object for ARI
        """

        LOGGER.debug("Performing test setup ...")

        # Disable ARI auto-exceptions on HTTP errors
        ari.set_allow_errors(True)

        # Create a baseline bridge using bridge 0's id and name, but no type
        self.__create_bridge(ari,
                             'ok',
                             None,
                             self.baseline_bridges[0].uid,
                             name=self.baseline_bridges[0].name)

        # Create a baseline bridge without a name or type, using bridge 1's id
        self.__create_bridge(ari,
                             'ok',
                             None,
                             self.baseline_bridges[1].uid)

        # Create a baseline bridge using bridge 2's id, name, and type
        self.__create_bridge(ari,
                             'ok',
                             None,
                             self.baseline_bridges[2].uid,
                             name=self.baseline_bridges[2].name,
                             type=self.baseline_bridges[2].bridge_type)

        # Create a baseline bridge without a name, using bridge 3's id and type
        self.__create_bridge(ari,
                             'ok',
                             None,
                             self.baseline_bridges[3].uid,
                             name=self.baseline_bridges[3].name,
                             type=self.baseline_bridges[3].bridge_type)
        return

    def __tear_down_test(self, ari):
        """Tears down the state created during test setup.

        Restores ARI to its previous configuration and deletes the channel
        and bridges used during test execution.

        Keyword Arguments:
        ari   --  The wrapper object for ARI
        """
        LOGGER.debug("Performing test tear down ...")

        # Delete stasis channel used during the test
        ari.delete('channels', self.stasis_channel_id)

        # Delete bridges created during setup
        for i in range(len(self.baseline_bridges)):
            self.__delete_bridge(ari, self.baseline_bridges[i])

        # Restore ARI auto-exceptions on HTTP errors to its original value
        ari.set_allow_errors(self.__set_ari_allow_errors or False)

        LOGGER.debug("Test tear down complete.")
        return

    def __validate_server_response(self, expected, resp):
        """Validates the server response against the expected response.

        Keyword Arguments:
        expected   --  The expected http status code from the server.
        resp       --  The server response object.
        """

        expected_code = requests.codes[expected]
        if expected_code != resp.status_code:
            self.passing = False
            LOGGER.error("Test Failed. Expected %d (%s), got %s (%r)",
                         expected_code,
                         expected,
                         resp.status_code,
                         resp.json())
            return False
        return True

    def __delete_bridge(self, ari, bridge_info):
        """Deletes the bridge using the id of the bridge_info parameter.

        Keyword Arguments:
        ari           --  ARI wrapper object.
        bridge_info   --  Object containing info about the bridge to delete.
        """

        LOGGER.debug("Deleting bridge [%s] with id: [%s]",
                     bridge_info.name,
                     bridge_info.uid)
        ari.delete('bridges', bridge_info.uid)
        return

    def __create_bridge(self,
                        ari,
                        expected_status_code,
                        description,
                        bridge_uid,
                        **kwargs):

        """Creates a bridge with the expectation of failure.

        Using the parameters given, posts to the 'bridges' endpoint. Then,
        validates the server responded with the expected status code.

        Keyword Arguments:
        ari                   --  The wrapper object for ARI
        expected_status_code  --  The expected response from the server
        description           --  The text to write to the log
        bridge_uid            --  The unique id for the bridge to create
        kwargs                --  The query parameters
        """

        if description:
            LOGGER.debug(description)
        resp = ari.post('bridges',
                        bridge_uid,
                        **kwargs)
        self.__validate_server_response(expected_status_code, resp)
        return

    def __create_duplicate_bridges(self, ari, bridge_info):
        """Attempts to create a duplicate bridges.

        Using the details of an existing bridge provided by the bridge_info
        parameter, exercises fifteen state combinations to post to the
        'bridges' endpoint.

        Keyword Arguments:
        ari           --  The wrapper object for ARI
        bridge_info   --  The baseline bridge's information to use
        """

        LOGGER.debug("Current baseline bridge: [%s]", bridge_info.uid)

        # Test AD
        description = "Attempting to create a bridge using the same id \
                       as the current baseline bridge, but with no name \
                       and a different type specified"
        self.__create_bridge(ari,
                             'internal_server_error',
                             description,
                             bridge_info.uid,
                             type=self.DEFAULT_TEST_TYPE)

        # Test CD
        description = "Attempting to create a bridge, using the same id \
                       and name as the current baseline bridge but a \
                       different type specified"
        self.__create_bridge(ari,
                             'internal_server_error',
                             description,
                             bridge_info.uid,
                             name=bridge_info.name,
                             type=self.DEFAULT_TEST_TYPE)

        # Test DA
        description = "Attempting to create a bridge using the same id \
                       as the current baseline bridge but with a \
                       different name and no type specified"
        self.__create_bridge(ari,
                             'internal_server_error',
                             description,
                             bridge_info.uid,
                             name=self.DEFAULT_TEST_NAME)

        # Test DC
        description = "Attempting to create a bridge, using the same id \
                       and type as the current baseline bridge but with a \
                       different name specified"
        self.__create_bridge(ari,
                             'internal_server_error',
                             description,
                             bridge_info.uid,
                             name=self.DEFAULT_TEST_NAME,
                             type=bridge_info.bridge_type)

        # Test DD
        description = "Attempting to create a bridge using the same id \
                       as the current baseline bridge but with a \
                       different name and a different type"
        self.__create_bridge(ari,
                             'internal_server_error',
                             description,
                             bridge_info.uid,
                             name=self.DEFAULT_TEST_NAME,
                             type=self.DEFAULT_TEST_TYPE)
        return


def on_start(ari, event, test_object):
    """Event handler for the StasisStart event.

    Keyword Arguments:
    ari           --  The wrapper object for ARI
    event         --  The ARI StasisStart event object
    test_object   --  The TestCase object running the test
    """

    LOGGER.debug("Starting bridge error test: on_start(%r)", event)
    test = BridgeErrorTest(ari, event)
    result = test.run_test(ari)
    LOGGER.debug("Finsihed testing for bridge creation error conditions.")
    test_object.stop_reactor()
    return result
