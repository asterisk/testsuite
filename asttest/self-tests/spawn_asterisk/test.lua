-- test spawning asterisk

skip_if(not ast.exists(), "asterisk not found")

a = ast.new()
a:spawn()
posix.sleep(1)
res, err = a:term_or_kill()

print(res)
print(err)

if res == nil then
	fail("error running asterisk: " .. err)
elseif res ~= 0 then
	fail("asterisk exited with status " .. res)
end

pass("asterisk exited with status " .. res)

