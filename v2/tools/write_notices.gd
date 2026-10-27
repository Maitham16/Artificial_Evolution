extends SceneTree
# Regenerate after intentionally changing the pinned engine version.
func _initialize():
	var text="Artificial Evolution 2.0 — engine notices\nGenerated from Godot "+Engine.get_version_info().string+"\n\nGODOT ENGINE\n\n"+Engine.get_license_text()
	text+="\n\nTHIRD-PARTY COPYRIGHT INFORMATION\n\n"+JSON.stringify(Engine.get_copyright_info(),"\t",true)+"\n"
	var licenses=Engine.get_license_info()
	for key in licenses:
		text+="\n\nLICENSE: "+str(key)+"\n\n"+str(licenses[key])+"\n"
	var file=FileAccess.open("res://THIRD_PARTY_NOTICES.txt",FileAccess.WRITE)
	file.store_string(text.strip_edges()+"\n");file.close();quit()
