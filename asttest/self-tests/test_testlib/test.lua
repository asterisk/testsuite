-- test the test library
-- note: ts_log() and print() are not tested

require "asttest"

a = asttest.run("tests")

fail_if(a.results["fail_if_true"] ~= "fail", "fail_if(true) did nto cause a failure")
fail_if(a.results["fail_if_false"] ~= "pass", "fail_if(false) test failed, it should have passed")
fail_if(a.results["fail"] ~= "fail", "fail() did not cause a failure")
fail_if(a.results["pass"] ~= "pass", "pass() did not pass")
fail_if(a.results["skip"] ~= "skip", "skip() did not skip")
fail_if(a.results["error"] ~= "error", "error() did not result in an error")

