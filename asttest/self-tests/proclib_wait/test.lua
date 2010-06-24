-- test proc:wait

print("executing 'sleep 1' then wait()")
p = proc.exec("sleep", 1)
res, err = proc.perror(p:wait())
fail_if(res ~= 0, "error waiting for sleep, res == " .. tostring(res) .. " (expected 0)")

print("executing 'sleep 1', then wait(10)")
p = proc.exec("sleep", 1)
res, err = proc.perror(p:wait(10))
fail_if(res ~= nil and err ~= "timeout", "expected timeout")

print("executing 'sleep 1', then wait(1500)")
p = proc.exec("sleep", 1)
res, err = proc.perror(p:wait(1500))
fail_if(res ~= 0, "error waiting for sleep, res == " .. tostring(res) .. " (expected 0)")

