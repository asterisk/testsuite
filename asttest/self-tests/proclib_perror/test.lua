-- test proclib's ablity to detect missing and non-executable files

real_print = print
function print(msg)
	printed = true
	if msg ~= expected_msg then
		print = real_print
		fail("expected perror to print '" .. tostring(expected_msg) .. "' but got '" .. msg .. "' instead")
	end
end

function expect(msg)
	printed = false
	expected_msg = msg
end

function check()
	if not printed then
		print = real_print
		fail("expected perror to print '" .. tostring(expected_msg) .. "' but got nothing instead")
	end

	expected_msg = nil
	printed = false
end

function test_crash()
	real_print("testing crash")

	expect("process crashed (core dumped)")
	proc.perror(nil, "core")
	check()
end

function test_timeout()
	real_print("testing a timeout")
	expect(nil)
	local p = proc.exec("sleep", "1")
	proc.perror(p:wait(1))
end


function test_error_1()
	real_print("testing an error (1)")
	expect("error running process")
	proc.perror(nil, "error")
	check()
end

function test_error_2()
	real_print("testing an error (2)")
	expect("error running process (error)")
	proc.perror(nil, "error", "error", 1)
	check()
end

function test_signal_1()
	real_print("testing a signal (1)")
	expect("process terminated by signal 0")
	proc.perror(nil, 0)
	check()
end

function test_signal_2()
	real_print("testing a signal (2)")
	expect("process terminated by signal 15")
	local p = proc.exec("sleep", "1")
	proc.perror(p:term())
	check()
end

function test_unknown()
	real_print("testing an unknown error (2)")
	expect("error running process (unknown)")
	proc.perror(nil, "unknown")
	check()
end


test_crash()
test_timeout()

test_error_1()
test_error_2()

test_signal_1()
test_signal_2()

test_unknown()

