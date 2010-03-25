-- spawn the test driver to test expected failures

require "asttest"

a = asttest.run("tests")

fail_if(a.results["standard_xfail"] ~= "xfail", "standard xfail failed")

