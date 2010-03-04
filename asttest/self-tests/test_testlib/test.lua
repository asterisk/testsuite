-- test the test library
-- note: ts_log() and print() are not tested

package.path = package.path .. ";../?.lua"
require "asttest"

a = asttest.run("tests")

fail_if(a.results["fail_if_true"] ~= "fail")
fail_if(a.results["fail_if_false"] ~= "pass")
fail_if(a.results["check_true"] ~= "pass")
fail_if(a.results["check_false"] ~= "fail")
fail_if(a.results["fail"] ~= "fail")
fail_if(a.results["pass"] ~= "pass")
fail_if(a.results["skip"] ~= "skip")
fail_if(a.results["error"] ~= "error")

