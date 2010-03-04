-- spawn the test driver to test expected failures

package.path = package.path .. ";../?.lua"
require "asttest"

a = asttest.run("tests")

fail_if(a.results["standard_xfail"] ~= "xfail", "standard xfail failed")

