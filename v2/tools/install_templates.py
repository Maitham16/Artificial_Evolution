"""Install only verified macOS Godot templates; never touch the Python simulator."""
from pathlib import Path
import hashlib,json,urllib.request,zipfile
ROOT=Path(__file__).resolve().parents[1]
lock=json.loads((ROOT/'toolchain.lock.json').read_text())['macos_export_templates']
target=Path.home()/'Library/Application Support/Godot/export_templates'/lock['version']
def digest(path):
 h=hashlib.sha256()
 with path.open('rb') as f:
  for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
 return h.hexdigest()
if (target/'macos.zip').exists() and digest(target/'macos.zip')==lock['macos_zip_sha256']:
 print('Verified macOS export templates already installed:',target)
else:
 cache=ROOT/'.cache';cache.mkdir(exist_ok=True)
 archive=cache/'export-templates.tpz'
 if not archive.exists() or digest(archive)!=lock['sha256']:
  print('Downloading the official export templates (about 1.2 GB).',flush=True)
  urllib.request.urlretrieve(lock['url'],archive)
 if digest(archive)!=lock['sha256']:raise SystemExit('Export template checksum mismatch.')
 target.mkdir(parents=True,exist_ok=True)
 with zipfile.ZipFile(archive) as z:
  for name in ('macos.zip','version.txt'):(target/name).write_bytes(z.read('templates/'+name))
 assert digest(target/'macos.zip')==lock['macos_zip_sha256']
 print('Installed verified macOS templates:',target)
