-- spawn the test driver to test errors with various causes

package.path = package.path .. ";../?.lua"
require "asttest"

a = asttest.run("tests")

fail_if(a.results["generated_error"] ~= "error", "generated_error test failed")
fail_if(a.results["missing_test_file"] ~= "error", "missing test file test failed")
fail_if(a.results["runtime_error"] ~= "error", "runtime error test failed")
fail_if(a.results["syntax_error"] ~= "error", "syntax error test failed")

