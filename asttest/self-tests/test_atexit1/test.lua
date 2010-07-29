function do_error(result)
	fail_if(result.result ~= "fail", "expected result to be 'fail' here in do_error()")
	print("I am going to cause an error")
	this_will_cause_an_error()
end

function do_pass(result)
	fail_if(result.result ~= "fail", "expected result to be 'fail' here in do_pass()")
	pass()
end

test.atexit(do_error)
test.atexit(do_pass)
fail("this test shouldn't actually fail")

