function do_error()
	fail_if(result.result ~= "pass", "expected 'pass' here in do_error()")
	print("I am going to cause an error")
	this_will_cause_an_error()
end

function do_nothing()
	fail_if(result.result ~= "pass", "expected 'pass' here in do_nothing()")
end

test.atexit(do_error)
test.atexit(do_nothing)
test.atexit(do_nothing)
test.atexit(do_nothing)

