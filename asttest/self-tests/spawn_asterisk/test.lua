-- test spawning asterisk

skip_if(not ast.exists(), "asterisk not found")

a = ast.new()
a:spawn()
res, err = a:term_or_kill()

if res == nil then
	if err == "core" then
		fail("asterisk crashed")
	elseif type(err) == number then
		fail("asterisk exited from signal: " .. err)
	else
		fail("error running asterisk (err ==  " .. err .. ")")
	end
elseif res ~= 0 then
	fail("asterisk exited with status " .. res)
end

pass("asterisk exited with status " .. res)

