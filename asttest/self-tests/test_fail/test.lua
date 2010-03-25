-- spawn the test driver to test failure

require "asttest"

a = asttest.run("tests")

fail_if(a.results["standard_fail"] ~= "fail", "fail test failed, how ironic")

