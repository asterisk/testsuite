-- test proclib's ablity to read from stdout and stderr and write to stdin

print("reading from stdout")
test_string = "this is a test"
p = proc.exec_io("echo", "-n", test_string)
res = p.stdout:read("*a")

fail_if(test_string ~= res, "echo test failed: read '" .. res .. "' expected '" .. test_string .. "'") 


print("writing to stdin and reading from stdout")
p = proc.exec_io("cat")
p.stdin:write(test_string)
p.stdin:close()

res = p.stdout:read("*a")

fail_if(test_string ~= res, "cat test failed: read '" .. res .. "' expected '" .. test_string .. "'") 

print("reading from stderr")
p = proc.exec_io("cat", "this path should not exist")
res = p.stderr:read("*a")

print("read: " .. tostring(res))

fail_if(not res, "error reading from stderr")
fail_if(#res == 0, "result was a zero length string")

