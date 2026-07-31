"""Run the RTP payload merge characterization tests in Asterisk."""

import logging
import re


LOGGER = logging.getLogger(__name__)


class PayloadMergeUnitTestRunner:
    """Execute and validate the test_res_rtp payload merge test category."""

    def __init__(self, config, test_object):
        self.test_object = test_object
        self.ast = None
        test_object.register_start_observer(self.run)

    def run(self, ast):
        """Run the unit-test category after Asterisk has fully started."""
        self.ast = ast[0]
        deferred = self.ast.cli_exec(
            "test execute category /res/res_rtp/payload_merge/"
        )
        deferred.addCallback(self._rtp_completed)
        deferred.addCallback(
            lambda unused: self.ast.cli_exec(
                "test execute category /res/res_pjsip_session/payload_merge/"
            )
        )
        deferred.addCallbacks(self._pending_state_completed, self._failed)
        return deferred

    def _rtp_completed(self, cli):
        expected = re.search(
            r"\b3 Test\(s\) Executed\s+3 Passed\s+0 Failed\b",
            cli.output,
        )
        if not expected:
            raise RuntimeError(
                "Unexpected RTP payload merge unit-test output:\n{}".format(
                    cli.output
                )
            )
        return cli

    def _pending_state_completed(self, cli):
        expected = re.search(
            r"\b1 Test\(s\) Executed\s+1 Passed\s+0 Failed\b",
            cli.output,
        )
        if not expected:
            LOGGER.error(
                "Unexpected pending-state payload merge unit-test output:\n%s",
                cli.output,
            )
            self.test_object.set_passed(False)
        else:
            self.test_object.set_passed(True)
        self.test_object.stop_reactor()
        return cli

    def _failed(self, failure):
        LOGGER.error("Unable to execute payload merge unit tests: %s", failure)
        self.test_object.set_passed(False)
        self.test_object.stop_reactor()
        return failure
