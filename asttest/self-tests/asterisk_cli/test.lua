-- test spawning asterisk

skip_if(not ast.exists(), "asterisk not found")

a = ast.new()
a:spawn()

version, err = a:cli("core show version")
fail_if(not version, "error running asterisk -rx 'core show version': " .. tostring(err))
print(version)

res, err = proc.perror(a:term_or_kill())

if res == nil then
	fail("error running asterisk")
elseif res ~= 0 then
	fail("error, asterisk exited with status " .. res)
end

fail_if(a:cli("core show version"), "some how 'core show version' succeeded when asterisk was not running")

pass("asterisk exited with status " .. res)

