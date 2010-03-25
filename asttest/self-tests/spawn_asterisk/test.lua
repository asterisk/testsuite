-- test spawning asterisk

skip_if(not ast.exists(), "asterisk not found")

a = ast.new()
a:spawn()
res, err = proc.perror(a:term_or_kill())

if res == nil then
	fail("error running asterisk")
elseif res ~= 0 then
	fail("error, asterisk exited with status " .. res)
end

pass("asterisk exited with status " .. res)

