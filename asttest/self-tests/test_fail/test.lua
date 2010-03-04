-- spawn the test driver to test failure

package.path = package.path .. ";../?.lua"
require "asttest"

a = asttest.run("tests")

fail_if(a.results["standard_fail"] ~= "fail", "fail test failed, how ironic")

