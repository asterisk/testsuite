-- spawn the test driver to test unexpected successes

package.path = package.path .. ";../?.lua"
require "asttest"

a = asttest.run("tests")

fail_if(a.results["implicit_xpass"] ~= "xpass", "implicit xpass failed")
fail_if(a.results["explicit_xpass"] ~= "xpass", "explicit xpass failed")

