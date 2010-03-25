-- test matching various sequences of events

require "watcher"

dummy_manager = {}
dummy_manager.__index = dummy_manager

function dummy_manager:new()
	local dm = {
		handler = nil,
		done = false,
		events = {},
	}

	setmetatable(dm, self)
	return dm
end

function dummy_manager:queue(event)
	table.insert(self.events, event)
end

function dummy_manager:register_event(event, handler)
	self.handler = handler
end

function dummy_manager:unregister_event(event, handler)
	self.handler = nil
end

function dummy_manager:pump_messages()
	return true
end

function dummy_manager:process_events()
	if self.done then return end

	for i, event in ipairs(self.events) do
		self.handler(event)
	end

	self.done = true
end

function dummy_manager:resend()
	self.done = false
end

function standard_dm()
	local dm = dummy_manager:new()
	for i=1,10 do
		e = watcher.event.new("Event" .. i)
		e["header1"] = "value1"
		e["header2"] = "value2"
		e["header3"] = "value3"
		e["header4"] = "value4"
		dm:queue(e)
	end
	return dm
end

function empty_dm()
	return dummy_manager:new()
end

function expect_timeout(res, err)
	if res or err ~= "timeout" then
		fail("watcher did not timeout as expected\nres: " .. tostring(res) .. "\nerr: " .. tostring(err))
	end

	return res, err
end

function expect_success(res, err)
	if not res then
		fail("error running watcher: " .. err)
	end

	return res, err
end

function match_single_tree()
	-- build a tree with 10 nodes ordered in a single branch ending with
	-- one leaf, then match it

	print("matching a single ordered tree of nodes")

	local tree = watcher.etree:new(watcher.event.new("Event1"))
	local etree = tree
	for i=2,10 do
		etree = etree:add(watcher.event.new("Event" .. i))
	end

	expect_success(watcher.watch(standard_dm(), tree, 2))
end

function match_multiple_trees()
	-- build a tree two trees then match one of them

	print("matching multiple trees of ordered tree of nodes")

	function build_tree(start, finish)
		local tree = watcher.etree:new(watcher.event.new("Event" .. start))
		local etree = tree
		for i=start+1,finish do
			etree = etree:add(watcher.event.new("Event" .. i))
		end
	end

	expect_success(watcher.watch(standard_dm(), {build_tree(5, 10), build_tree(1, 3)}, 2))
end

function match_branching_tree_1()
	-- build a tree with a few nodes in a branching configuration

	print("matching an ordered tree with branching nodes")
	
	-- build a tree with a few nodes in a branching configuration mixed in
	-- with some out of order nodes

	print("matching events with headers (1)")

	local e = watcher.event.new

	-- build the follwing tree
	-- Event1
	--    |-> {Event4, Event2}
	--        |-> Event24
	--        |-> Event5 -> {Event7, Event8} -> Event10
	--    |-> Event3 -> Event12
	--    |-> Event23
	local tree = watcher.etree:new(watcher.event.new("Event1"))
	local t2 = tree:add{e("Event4"), e("Event2")}
	t2:add(e("Event24"))
	t2:add(e("Event5"))	   
	   :add{e("Event7"), e("Event8")}
	   :add(e("Event10"))
	tree:add(e("Event3"))
	   :add(e("Event12"))
	tree:add(e("Event23"))

	expect_success(watcher.watch(standard_dm(), tree, 2))

	local tree = watcher.etree:new(watcher.event.new("Event1"))
	local etree = tree
	for i=2,10 do
		etree = etree:add(watcher.event.new("Event" .. i))
	end

	expect_success(watcher.watch(standard_dm(), tree, 2))
end

function match_out_of_order()
	-- match 9 events out of order followed by a 10th event
	
	print("testing matching out of order")

	-- build the events table with Event9 through Event1 in that order
	local events = {}
	for i=9,1,-1 do
		table.insert(events, watcher.event.new("Event" .. i))
	end

	local tree = watcher.etree:new(events)
	tree:add(watcher.event.new("Event10"))

	expect_success(watcher.watch(standard_dm(), tree, 2))

	-- check and make sure every event was actually matched
	for i=1,9 do
		if not tree.received[i] then
			fail("tree.multi[" .. i .. "] is: " .. tostring(tree.multi[i]))
		end
	end
end

function match_branching_out_of_order_tree_1()
	-- build a tree with a few nodes in a branching configuration mixed in
	-- with some out of order nodes

	print("matching an ordered tree with branching nodes and out of order nodes")

	local e = watcher.event.new

	-- build the follwing tree
	-- Event1
	--    |-> {Event4, Event2} -> Event5 -> {Event7, Event8} -> Event10
	--    |-> Event3 -> Event12
	--    |-> Event23
	local tree = watcher.etree:new(watcher.event.new("Event1"))
	tree:add{e("Event4"), e("Event2")}
	   :add(e("Event5"))
	   :add{e("Event7"), e("Event8")}
	   :add(e("Event10"))
	tree:add(e("Event3"))
	   :add(e("Event12"))
	tree:add(e("Event23"))

	expect_success(watcher.watch(standard_dm(), tree, 2))
end

function match_headers_1()
	-- build a tree with a few nodes in a branching configuration mixed in
	-- with some out of order nodes

	print("matching events with headers (1)")

	local e = function(event)
		local e = watcher.event.new(event)
		e["header1"] = "value1"
		e["header2"] = "value2"
		e["header3"] = "value3"
		e["header4"] = "value4"
		return e
	end

	-- build the follwing tree
	-- Event1
	--    |-> {Event4, Event2} -> Event5 -> {Event7, Event8} -> Event10
	--    |-> Event3 -> Event12
	--    |-> Event23
	local tree = watcher.etree:new(watcher.event.new("Event1"))
	tree:add{e("Event4"), e("Event2")}
	   :add(e("Event5"))
	   :add{e("Event7"), e("Event8")}
	   :add(e("Event10"))
	tree:add(e("Event3"))
	   :add(e("Event12"))
	tree:add(e("Event23"))

	expect_success(watcher.watch(standard_dm(), tree, 2))
end

function match_headers_2()
	-- build a tree with a few nodes in a branching configuration mixed in
	-- with some out of order nodes

	print("matching events with headers (2)")

	local e = function(event)
		local e = watcher.event.new(event)
		e["header1"] = "value1"
		e["header2"] = "value2"
		e["header3"] = "value3"
		e["header4"] = "won't match"
		return e
	end

	-- build the follwing tree
	-- Event1
	--    |-> {Event4, Event2} -> Event5 -> {Event7, Event8} -> Event10
	--    |-> Event3 -> Event12
	--    |-> Event24
	local tree = watcher.etree:new(watcher.event.new("Event1"))
	tree:add{e("Event4"), e("Event2")}
	   :add(e("Event5"))
	   :add{e("Event7"), e("Event8")}
	   :add(e("Event10"))
	tree:add(e("Event3"))
	   :add(e("Event12"))
	tree:add(e("Event23"))

	expect_timeout(watcher.watch(standard_dm(), tree, 2))
end

function test_timeout_1()
	-- build a tree starting with 'Event10' which will come last causing a
	-- timeout

	print("testing a timeout (1)")

	local tree = watcher.etree:new(watcher.event.new("Event10"))
	local etree = tree
	for i=1,9 do
		etree = etree:add(watcher.event.new("Event" .. i))
	end

	expect_timeout(watcher.watch(standard_dm(), tree, 2))
end

function test_timeout_2()
	-- don't send any events causing a timeout

	print("testing a timeout (2)")

	local tree = watcher.etree:new(watcher.event.new("Event10"))
	local etree = tree
	for i=1,9 do
		etree = etree:add(watcher.event.new("Event" .. i))
	end

	expect_timeout(watcher.watch(empty_dm(), tree, 2))
end

function match_with_function_1()
	print("testing matching with a matching function (1)")

	local tree = watcher.etree:new(function(e)
		return true
	end)

	expect_success(watcher.watch(standard_dm(), tree, 2))
end

function match_with_function_2()
	print("testing matching headers with a matching function (1)")

	local event = watcher.event.new("Event3")
	event["header1"] = function(value)
		return value == "value1"
	end

	local tree = watcher.etree:new(event)

	expect_success(watcher.watch(standard_dm(), tree, 2))
end

match_single_tree()
match_multiple_trees()
match_branching_tree_1()
match_out_of_order()
match_branching_out_of_order_tree_1()
match_headers_1()
match_headers_2()

test_timeout_1()
test_timeout_2()

match_with_function_1()
match_with_function_2()


