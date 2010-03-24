-- test spawning asterisk

skip_if(not ast.exists(), "asterisk not found")

a = ast.new()
a:spawn()
res, err = a:term_or_kill()

if res == nil then
	fail("error running asterisk: " .. err)
elseif res ~= 0 then
	fail("asterisk exited with status " .. res)
end

pass("asterisk exited with status " .. res)

