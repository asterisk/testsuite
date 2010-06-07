-- test spawning asterisk

skip_if(not ast.exists(), "asterisk not found")

a = ast.new()
a:spawn()

version = a:cli("core show version")
fail_if(not version, "error running asterisk -rx 'core show version' or error reading the output of asterisk -rx 'core show version'")
print(version)

res, err = proc.perror(a:term_or_kill())

if res == nil then
	fail("error running asterisk")
elseif res ~= 0 then
	fail("error, asterisk exited with status " .. res)
end

pass("asterisk exited with status " .. res)

