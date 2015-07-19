; res_pjsip_config_wizard implicitly uses an in memory sorcery wizard
; to cache configuration items. This would cause the test to fail,
; as we need to verify that a wizard that does support object creation
; will result in a 403 response.
noload => res_pjsip_config_wizard
