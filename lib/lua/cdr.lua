-- load asterisk csv cdr file and parse it

module(..., package.seeall)

function new(a)
	return cdr:new(a)
end

cdr = {}
cdr.__metatable = "cdr"
function cdr:new(a)
	local c = {
		path = a:path("/var/log/asterisk/cdr-csv/Master.csv"),
		_records = {},
	}
	setmetatable(c, self)

	local res, err = c:_parse()
	if not res then
		return res, err
	end
	return c
end

function cdr:len()
	return self:__len()
end

function cdr:__len()
	return #self._records
end

function cdr:__index(i)
	if type(i) == "number" then
		return rawget(self, "_records")[i]
	end
	return rawget(cdr, i)
end

function cdr:ipairs()
	return ipairs(self._records)
end

function cdr:records()
	local i = 1
	local f = function(s)
		local r = s._records[i]
		i = i + 1
		return r
	end
	return f, self
end

function cdr:_parse()
	local f, err = io.open(self.path)
	if not f then
		return f, err
	end

	local count = 1
	for line in f:lines() do
		local r, err = cdr_record:new(line)
		if not r then
			return r, ("error parsing cdr on line %s (%s)"):format(count, err)
		end
		table.insert(self._records, r)
		count = count + 1
	end
	return self
end

cdr_record = {}
function cdr_record:new(line)
	local r = {
		index = {
			"accountcode",
			"src",
			"dst",
			"dcontext",
			"clid",
			"channel",
			"dstchannel",
			"lastapp",
			"lastdata",
			"start",
			"answer",
			"end",
			"duration",
			"billsec",
			"disposition",
			"amaflags",
			"uniqueid",
			"userfield",
		},
		data = {},
	}

	setmetatable(r, self)
	
	self._process_index(r)
	local res, err = self._parse(r, line)
	if not res then
		return res, err
	end

	return r
end

function cdr_record:_parse(line)
	-- this algorithm is adapted from Programming in Lua (1st Edition)
	-- chapter 20, section 4
	
	line = line .. ',' -- ending comma
	local start = 1
	repeat
		-- next field is quoted? (start with `"'?)
		if line:find('^"', start) then
			local a, c
			local i  = start
			repeat
				-- find closing quote
				a, i, c = line:find('"("?),', i+1)
			until c ~= '"'    -- quote not followed by quote?
			if not i then return nil, 'unmatched "' end
			local f = line:sub(start+1, i-2)
			table.insert(self.data, (f:gsub('""', '"')))
			start = i+1
		else                -- unquoted; find next comma
			local nexti = line:find(',', start)
			table.insert(self.data, line:sub(start, nexti-1))
			start = nexti + 1
		end
	until start > line:len()
	return self.data
end

function cdr_record:_process_index()
	for k, v in ipairs(self.index) do
		self.index[v] = k
	end
end

function cdr_record:__index(i)
	if type(i) == "number" then
		return rawget(self, "data")[i]
	end
	return rawget(self, "data")[rawget(self, "index")[i]]
end

-- put cdr in the ast table too
_G.ast.cdr = _G.cdr

