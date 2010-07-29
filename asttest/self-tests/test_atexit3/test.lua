function do_fail()
	fail_if(result.result ~= "pass", "result in do_fail() was not 'pass'")
	fail()
end

function do_pass(result)
	fail_if(result.result ~= "pass", "result in do_pass() was not 'pass'")
	pass()
end

function do_nothing()
	fail_if(result.result ~= "pass", "result in do_nothing() was not 'pass'")
end

test.atexit(do_fail)
test.atexit(do_pass)
test.atexit(do_pass)
test.atexit(do_nothing)

