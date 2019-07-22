; Don't load pbx_lua.so as the extensions.lua sample file conflicts with this test
noload => pbx_lua.so

; Might as well not load AEL modules either to prevent the possiblity of future conflicts
noload => pbx_ael.so
noload => res_ael_share.so
