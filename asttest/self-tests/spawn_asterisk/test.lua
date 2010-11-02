-- test spawning asterisk

skip_if(not ast.exists(), "asterisk not found")

count = 5
instances = {}
for i=1,count do
	print("starting asterisk instance " .. i)
	local a = ast.new()
	a:spawn()
	table.insert(instances, a)
end

for i=1,count do
	print("killing asterisk instance " .. i)
	local a = instances[i]
	local res, err = proc.perror(a:term_or_kill())

	if res == nil then
		fail("error running asterisk")
	elseif res ~= 0 then
		fail("error, asterisk exited with status " .. res)
	end
end

