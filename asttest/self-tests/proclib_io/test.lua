-- test proclib's ablity to read from stdout and stderr and write to stdin

test_string = "this is a test"
p = proc.exec_io("echo", "-n", test_string)
res = p.stdout:read("*a")

fail_if(test_string ~= res, "echo test failed: read '" .. res .. "' expected '" .. test_string .. "'") 


p = proc.exec_io("cat")
p.stdin:write(test_string)
p.stdin:close()

res = p.stdout:read("*a")

fail_if(test_string ~= res, "cat test failed: read '" .. res .. "' expected '" .. test_string .. "'") 

