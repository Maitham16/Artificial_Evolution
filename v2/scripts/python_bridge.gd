extends Node
## Nonblocking transport and owned Python-process lifecycle. No model rules.
signal frame_received(frame: Dictionary)
signal response_received(response: Dictionary)
signal catalog_received(catalog: Dictionary)
signal status_changed(status: String, detail: String)
const PROTOCOL=1
const MAX_BUFFER=16*1024*1024
var peer:=StreamPeerTCP.new()
var incoming:=PackedByteArray()
var outgoing:=PackedByteArray()
var status="stopped"
var detail=""
var endpoint={}
var endpoint_path=""
var backend_pid=-1
var request_id=0
var started_at=0.0
var last_message=0.0
var last_ping=0.0
var engine_root=""
var python=""
var catalog={}
var authenticated=false
var saw_connection=false
var seen_births=-1
var seen_run=""
var auto_save=true

func _now() -> float:return Time.get_ticks_usec()/1000000.0

func _set_status(value: String,description: String="") -> void:
	status=value;detail=description;status_changed.emit(value,description)

func discover() -> Dictionary:
	var settings={}
	var path="user://engine.json"
	if FileAccess.file_exists(path):
		var parsed=JSON.parse_string(FileAccess.get_file_as_string(path))
		if parsed is Dictionary:settings=parsed
	var source=ProjectSettings.globalize_path("res://").trim_suffix("/").get_base_dir()
	if FileAccess.file_exists(source.path_join("research_session.py")):settings.repository=source
	if not OS.get_environment("AE_ENGINE_ROOT").is_empty():settings.repository=OS.get_environment("AE_ENGINE_ROOT")
	if not OS.get_environment("AE_PYTHON").is_empty():settings.python=OS.get_environment("AE_PYTHON")
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--engine-root="):settings.repository=arg.trim_prefix("--engine-root=")
		elif arg.begins_with("--python="):settings.python=arg.trim_prefix("--python=")
		elif arg=="--no-auto-save":auto_save=false
	if settings.has("repository") and not settings.has("python"):settings.python=str(settings.repository).path_join(".venv/bin/python")
	return settings

func launch(repository: String,interpreter: String) -> void:
	if backend_pid>0 and OS.is_process_running(backend_pid):
		_set_status("error","The current Python process is still running. Reconnect or close it first.");return
	engine_root=repository.simplify_path();python=interpreter.simplify_path()
	if not FileAccess.file_exists(engine_root.path_join("research_session.py")) or not FileAccess.file_exists(engine_root.path_join("v2/backend/engine_bridge.py")):
		_set_status("error","Choose the Artificial_Evolution repository containing research_session.py and v2/backend/engine_bridge.py.");return
	if not FileAccess.file_exists(python):
		_set_status("error","Python was not found. Choose this repository's .venv/bin/python, or run setup_macos.sh.");return
	peer=StreamPeerTCP.new();incoming.clear();outgoing.clear();endpoint={};authenticated=false;saw_connection=false;seen_births=-1
	var directory=ProjectSettings.globalize_path("user://bridge")
	DirAccess.make_dir_recursive_absolute(directory)
	endpoint_path=directory.path_join("endpoint-%d-%s.json" % [OS.get_process_id(),Crypto.new().generate_random_bytes(8).hex_encode()])
	var exports=ProjectSettings.globalize_path("user://python-runs")
	var args=PackedStringArray(["-u",engine_root.path_join("v2/backend/engine_bridge.py"),"--ready-file",endpoint_path,"--export-root",exports,"--owner-pid",str(OS.get_process_id())])
	if not auto_save:args.append("--no-auto-save")
	backend_pid=OS.create_process(python,args)
	if backend_pid<=0:_set_status("error","Could not start Python. Verify the interpreter and dependencies.");return
	started_at=_now();last_message=started_at
	_set_status("starting","Starting the existing Python simulation engine…")

func remember() -> void:
	var file=FileAccess.open("user://engine.json",FileAccess.WRITE)
	if file:file.store_string(JSON.stringify({"repository":engine_root,"python":python},"\t")+"\n");file.close()

func reconnect() -> void:
	if backend_pid>0 and OS.is_process_running(backend_pid) and not endpoint.is_empty():
		peer.disconnect_from_host();peer=StreamPeerTCP.new();incoming.clear();outgoing.clear();authenticated=false;saw_connection=false;seen_births=-1
		started_at=_now();_connect()
	else:launch(engine_root,python)

func _connect() -> void:
	if int(endpoint.get("protocol",0))!=PROTOCOL:_set_status("error","Python bridge protocol differs from this renderer.");return
	var error=peer.connect_to_host("127.0.0.1",int(endpoint.port))
	if error!=OK:_set_status("error","Cannot connect to the local Python engine: "+error_string(error));return
	_set_status("connecting","Connecting to Python on this Mac…")

func request(command: String,data: Dictionary={}) -> int:
	if command!="hello" and not authenticated:return -1
	request_id+=1
	var value=data.duplicate(true);value.cmd=command;value.id=request_id
	outgoing.append_array((JSON.stringify(value)+"\n").to_utf8_buffer())
	if outgoing.size()>MAX_BUFFER:_fail("Python command queue exceeded its limit.")
	return request_id

func _fail(message: String) -> void:
	peer.disconnect_from_host();authenticated=false;_set_status("disconnected",message)

func _deliver(value) -> void:
	if not value is Dictionary:_fail("Python sent an invalid message.");return
	last_message=_now()
	if value.get("type","")=="response":
		if value.get("ok",false) and value.has("catalog"):
			catalog=value.catalog;authenticated=true;remember();_set_status("ready","Python engine "+str(catalog.engine_version)+" connected")
			catalog_received.emit(catalog)
		if value.has("frame"):_deliver(value.frame)
		response_received.emit(value)
	elif value.get("type","")=="frame":
		if int(value.get("protocol",0))!=PROTOCOL:_fail("Incompatible Python snapshot protocol.");return
		frame_received.emit(value)
		if seen_run!=str(value.run_id):seen_run=str(value.run_id);seen_births=-1
		var count=int(value.get("birth_count",0))
		if count!=seen_births:
			seen_births=count;request("seen",{"count":count,"run_id":str(value.run_id)})
	else:_fail("Python sent an unknown message type.")

func _process(_delta: float) -> void:
	var now=_now()
	if status=="starting":
		if FileAccess.file_exists(endpoint_path):
			var data=JSON.parse_string(FileAccess.get_file_as_string(endpoint_path))
			if data is Dictionary and data.has("port") and data.has("token"):endpoint=data;_connect()
		if backend_pid>0 and not OS.is_process_running(backend_pid):_set_status("error","Python exited during startup. Verify .venv dependencies with v2/tools/configure_engine.py.")
		elif now-started_at>20:_set_status("error","Python startup timed out. Check the repository, interpreter, and terminal output.")
		return
	if status not in ["connecting","authenticating","ready"]:return
	peer.poll()
	var connection=peer.get_status()
	if connection==StreamPeerTCP.STATUS_CONNECTED:
		if not saw_connection:
			saw_connection=true;peer.set_no_delay(true);_set_status("authenticating","Authenticating the local engine…")
			request("hello",{"protocol":PROTOCOL,"token":endpoint.token})
		var available=peer.get_available_bytes()
		if available>0:
			var result=peer.get_partial_data(mini(available,MAX_BUFFER))
			if result[0]!=OK:_fail("Python connection read failed.");return
			incoming.append_array(result[1])
			if incoming.size()>MAX_BUFFER:_fail("Python snapshot exceeded the buffer limit.");return
		var end=incoming.find(10)
		var count=0
		while end>=0 and count<128:
			var raw=incoming.slice(0,end).get_string_from_utf8();incoming=incoming.slice(end+1)
			_deliver(JSON.parse_string(raw));count+=1
			if status=="disconnected":return
			end=incoming.find(10)
		if not outgoing.is_empty():
			var result=peer.put_partial_data(outgoing)
			if result[0]!=OK:_fail("Python connection write failed.");return
			outgoing=outgoing.slice(int(result[1]))
		if authenticated and now-last_ping>2:request("ping");last_ping=now
		if now-last_message>15:_fail("Python stopped responding. The view is frozen; reconnect to continue.")
	elif connection==StreamPeerTCP.STATUS_ERROR or (saw_connection and connection==StreamPeerTCP.STATUS_NONE):
		_fail("Python disconnected. The last state is frozen; use Reconnect.")
	elif now-started_at>20:_fail("Could not establish the Python connection.")

func detach() -> void:
	peer.disconnect_from_host();authenticated=false;_set_status("stopped")
