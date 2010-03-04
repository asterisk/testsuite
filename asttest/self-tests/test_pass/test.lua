-- spawn the test driver to test passing

package.path = package.path .. ";../?.lua"
require "asttest"

a = asttest.run("tests")

fail_if(a.results["explicit_pass"] ~= "pass", "pass test failed")
fail_if(a.results["implicit_pass"] ~= "pass", "pass test failed")

