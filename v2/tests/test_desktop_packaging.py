"""Check the desktop lock and prevent destructive installer failures."""
from pathlib import Path
import hashlib
import importlib.util
import json
import plistlib
import os
import runpy
import tempfile
import unittest
from unittest.mock import patch
import zipfile

V2=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('desktop_installer',V2/'tools/install_macos.py')
installer=importlib.util.module_from_spec(spec);spec.loader.exec_module(installer)


class DesktopPackagingTests(unittest.TestCase):
    def test_runtime_lock_matches_unchanged_root_requirements_and_bundled_licenses(self):
        lock=json.loads((V2/'runtime.lock.json').read_text())
        self.assertEqual(hashlib.sha256((V2.parent/'requirements.txt').read_bytes()).hexdigest(),lock['requirements_sha256'])
        self.assertEqual(len(lock['wheels']),13)
        self.assertEqual(lock['python']['architecture'],'arm64')
        for name,expected in lock['license_files'].items():
            self.assertEqual(hashlib.sha256((V2/'assets/runtime-licenses'/name).read_bytes()).hexdigest(),expected)

    def test_original_2d_cache_stays_outside_signed_engine_and_respects_explicit_override(self):
        with patch.dict(os.environ):
            os.environ.pop('MPLCONFIGDIR',None)
            runpy.run_path(str(V2/'backend/runtime_sitecustomize.py'))
            self.assertIn('Library/Caches/ArtificialEvolution2',os.environ['MPLCONFIGDIR'])
            os.environ['MPLCONFIGDIR']='/explicit/user/cache'
            runpy.run_path(str(V2/'backend/runtime_sitecustomize.py'))
            self.assertEqual(os.environ['MPLCONFIGDIR'],'/explicit/user/cache')

    def test_installer_rejects_wrong_archive_before_changing_existing_application(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);archive=root/'app.zip';archive.write_bytes(b'bad archive')
            (root/'desktop-manifest.json').write_text(json.dumps({'archive_sha256':'wrong'}))
            old=root/'Existing.app';old.mkdir();(old/'keep').write_text('old app')
            with self.assertRaisesRegex(ValueError,'checksum mismatch'):installer.install(archive,old)
            self.assertEqual((old/'keep').read_text(),'old app')

    def test_failed_post_install_validation_restores_previous_application(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);archive=root/'app.zip';old=root/'Existing.app';(old/'Contents').mkdir(parents=True)
            info=plistlib.dumps({'CFBundleIdentifier':'org.maitham.artificialevolution2'})
            (old/'Contents/Info.plist').write_bytes(info);(old/'keep').write_text('old app')
            with zipfile.ZipFile(archive,'w') as z:
                z.writestr('New.app/Contents/Info.plist',info)
                z.writestr('New.app/new','new app')
            with patch.object(installer,'validate_app',side_effect=[None,ValueError('deliberate failed final verification')]):
                with self.assertRaisesRegex(ValueError,'failed final verification'):installer.install(archive,old)
            self.assertEqual((old/'keep').read_text(),'old app')
            self.assertFalse((old/'new').exists())

if __name__=='__main__':unittest.main()
