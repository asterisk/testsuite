
require "watcher"

function check_userevent(e)
	if e["UserEvent"] == "FaxStatus" then
		if e["status"] ~= "SUCCESS" then
			print(("%s failed with status: %s\nerror: %s (%s)"):format(e["application"], e["status"], e["error"], e["statusstr"]))
			fax_error = true
		end

		return true
	end

	return false
end

function a(host1, host2)
   local a = ast.new()
   a:generate_asterisk_conf()
   a:generate_manager_conf()
   a["asterisk.conf"]["options"]["verbose"] = 10
   a["asterisk.conf"]["options"]["debug"] = 10
   a["asterisk.conf"]["options"]["internal_timing"] = "yes"

   -- sip.conf
   local c = a:new_config("sip.conf")
   local s = c:new_section("general")
   s["bindaddr"] = host1
   s["t38pt_udptl"] = "yes,none"
   s["disallow"] = "all"
   s["allow"] = "gsm"
   
   s = c:new_section("fax")
   s["type"] = "peer"
   s["context"] = "local-receivefax"
   s["host"] = host2
   s["t38pt_udptl"] = "yes,none"
   s["disallow"] = "all"
   s["allow"] = "gsm"
   s["insecure"] = "invite"
   s["qualify"] = "no"

   -- extensions.conf
   c = a:new_config("extensions.conf")
   s = c:new_section("receivefax")
   s["exten"] = "1234,1,noop"
   s["exten"] = "1234,n,ReceiveFax(receive.tiff)"
   
   s["exten"] = "h,1,noop"
   s["exten"] = "h,n,UserEvent(FaxStatus,application: ReceiveFax,status: ${FAXOPT(status)},statusstr: ${FAXOPT(statusstr)},error: ${FAXOPT(error)})"
   
   s = c:new_section("local-receivefax")
   s["exten"] = "1234,1,noop"
   s["exten"] = "1234,n,Dial(local/1234@receivefax)"

   s = c:new_section("sendfax")
   s["exten"] = "1234,1,noop"
   s["exten"] = "1234,n,SendFax(send.tiff)"

   s["exten"] = "h,1,noop"
   s["exten"] = "h,n,UserEvent(FaxStatus,application: SendFax,status: ${FAXOPT(status)},statusstr: ${FAXOPT(statusstr)},error: ${FAXOPT(error)})"
   
   s = c:new_section("local-sendfax")
   s["exten"] = "1234,1,noop"
   s["exten"] = "1234,n,Dial(local/1234@sendfax)"

   -- modules.conf
   c = a:new_config("modules.conf")
   s = c:new_section("modules")
   s["autoload"] = "no"
   s["load"] = "pbx_config.so"

   s["load"] = "res_features.so"

   s["load"] = "res_timing_dahdi.so"
   s["load"] = "res_timing_timerfd.so"
   s["load"] = "res_timing_pthread.so"

   s["load"] = "codec_ulaw.so"
   s["load"] = "codec_gsm.so"

   s["load"] = "app_dial.so"
   s["load"] = "func_callerid.so"
   s["load"] = "res_rtp_asterisk.so"
   s["load"] = "chan_sip.so"
   s["load"] = "chan_local.so"

   s["load"] = "app_userevent.so"
   s["load"] = "res_fax.so"
   s["load"] = "res_fax_spandsp.so"

   return a
end

action = ast.manager.action

a1 = a("127.0.0.1", "127.0.0.2")
a2 = a("127.0.0.2", "127.0.0.1")

a1:spawn()
a2:spawn()

a1:cli("fax set debug on")
a1:cli("sip debug")

a2:cli("fax set debug on")
a2:cli("sip debug")


m = check("error connecting to asterisk", a1:manager_connect())

r = check("error authenticating", m(action.login()))
if r["Response"] ~= "Success" then
	error("error authenticating: " .. r["Message"])
end

a = action:new("originate")
a["Channel"] = "sip/1234@fax"
a["Context"] = "local-sendfax"
a["Exten"] = "1234"
a["Priority"] = "1"

r = check("error sending fax call", m(a))
if r["Response"] ~= "Success" then
	error("error sending fax call: " .. r["Message"])
end

-- wait for the FaxStatus UserEvent for 90 seconds
res, err = watcher.watch(m, watcher.etree:new(check_userevent), 90000)
if not res then
	fail("error while waiting for FaxStatus UserEvent: " .. err)
end

-- the fax_error variable is set in the check_userevent() function
fail_if(fax_error, "error faxing via a local channel")

