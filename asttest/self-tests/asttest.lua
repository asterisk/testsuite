-- spawn the test driver and parse the results

module(..., package.seeall)

asttest = {}
function asttest:new(test_dir)
	local a = {
		dir = test_dir,
		tests = {},
		results = {},
		totals = {
			["pass"] = 0,
			["fail"] = 0,
			["xpass"] = 0,
			["xfail"] = 0,
			["skip"] = 0,
			["error"] = 0,
			["total"] = 0,
		},
	}
	setmetatable(a, self)
	self.__index = self
	return a
end

function asttest:parse_output()
	for test, result in string.gmatch(self.output, "%d+%.%s+(%S+)%s+(%S+)\n") do
		table.insert(self.tests, test)

		self.results[test] = result

		self.totals[result] = self.totals[result] + 1
		self.totals.total = self.totals.total + 1
	end
end

function asttest:spawn()
	local output = io.popen("../../asttest 2>&1 " .. self.dir)
	if not output then
		return true, "error running asttest"
	end

	self.log = self.dir .. "/asttest.log"
	self.output = output:read("*a")
	self:parse_output()
	return false
end

function run(dir)
	local a = asttest:new(dir)
	e, reason = a:spawn()
	if e then
		return nil
	else
		return a
	end
end

