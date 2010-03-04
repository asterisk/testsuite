-- spawn the test driver to test skip functionality

package.path = package.path .. ";../?.lua"
require "asttest"

a = asttest.run("tests")

fail_if(a.results["standard_skip"] ~= "skip", "skip test failed")

