-- spawn the test driver to test skip functionality

require "asttest"

a = asttest.run("tests")

fail_if(a.results["standard_skip"] ~= "skip", "skip test failed")

