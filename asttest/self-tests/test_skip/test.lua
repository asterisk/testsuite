-- spawn the test driver to test skip functionality

require "asttest"

a = asttest.run("tests")

fail_if(a.results["standard_skip"] ~= "skip", "skip test failed")
fail_if(a.results["_auto_skip"] ~= "skip", "_auto_skip was not automatically skipped")
fail_if(a.results[".hidden_skip"] ~= nil, ".hidden_skip was not automatically and silently skipped")

