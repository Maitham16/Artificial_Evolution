"""Keep the README redesign from weakening original-code/document preservation."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

TOOL = Path(__file__).resolve().parents[1] / 'tools/verify_original.py'
START = b'<!-- V1-README-ARCHIVE:START -->\n'
END = b'<!-- V1-README-ARCHIVE:END -->'


class OriginalPreservationTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory(prefix='ae2-readme-preservation-')
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)
        self.originals = {'README.md': b'# Original project\n\nV1 methods and results.\n',
                          'engine.py': b'PHYSICS_STEP = 1 / 60\n',
                          'docs/USER_GUIDE.md': b'# Original V1 user guide\n'}
        for name, content in self.originals.items():
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        destination = self.root / 'v2/tools/verify_original.py'
        destination.parent.mkdir(parents=True)
        shutil.copyfile(TOOL, destination)
        baseline = self.root / 'v2/docs/inspection/baseline.json'
        baseline.parent.mkdir(parents=True)
        baseline.write_text(json.dumps(dict(commit='fixture', tracked_files=list(self.originals),
            original_files={name: dict(sha256=hashlib.sha256(content).hexdigest())
                            for name, content in self.originals.items()})))
        subprocess.run(['git', 'init', '--quiet', str(self.root)], check=True)
        subprocess.run(['git', 'add', '--', *self.originals], cwd=self.root, check=True)

    def redesign(self, original=None):
        original = self.originals['README.md'] if original is None else original
        (self.root / 'README.md').write_bytes(b'# New landing page\n<details>\n' + START + original + END + b'\n</details>\n')

    def verify(self):
        result = subprocess.run([sys.executable, str(self.root / 'v2/tools/verify_original.py')],
                                cwd=self.root, text=True, capture_output=True, check=False)
        return result.returncode, json.loads(result.stdout)

    def test_original_files_still_pass_without_an_archive(self):
        code, report = self.verify()
        self.assertEqual(code, 0)
        self.assertEqual(report['preserved_documentation_archives'], [])

    def test_redesign_passes_only_with_the_exact_original_readme(self):
        self.redesign()
        code, report = self.verify()
        self.assertEqual(code, 0)
        self.assertEqual(report['preserved_documentation_archives'][0]['path'], 'README.md')
        self.assertEqual(report['preserved_documentation_archives'][0]['original_sha256'],
                         hashlib.sha256(self.originals['README.md']).hexdigest())

    def test_changed_archived_v1_text_is_rejected(self):
        self.redesign(self.originals['README.md'].replace(b'results', b'invented results'))
        code, report = self.verify()
        self.assertEqual(code, 1)
        self.assertIn({'path': 'README.md', 'error': 'changed'}, report['problems'])

    def test_missing_duplicate_or_reversed_markers_are_rejected(self):
        for data in (START + self.originals['README.md'],
                     START + self.originals['README.md'] + END + START + END,
                     END + START + self.originals['README.md'],
                     self.originals['README.md'] + b'\nUndelimited new content'):
            with self.subTest(data=data):
                (self.root / 'README.md').write_bytes(data)
                code, _ = self.verify()
                self.assertEqual(code, 1)

    def test_archiving_does_not_allow_changes_to_engine_or_v1_guides(self):
        self.redesign()
        for name in ('engine.py', 'docs/USER_GUIDE.md'):
            with self.subTest(path=name):
                path = self.root / name
                path.write_bytes(START + self.originals[name] + END)
                code, report = self.verify()
                self.assertEqual(code, 1)
                self.assertIn({'path': name, 'error': 'changed'}, report['problems'])
                path.write_bytes(self.originals[name])

    def test_new_tracked_files_outside_v2_are_still_rejected(self):
        self.redesign()
        (self.root / 'new_engine.py').write_text('UNREVIEWED_RULE = 1\n')
        subprocess.run(['git', 'add', 'new_engine.py'], cwd=self.root, check=True)
        code, report = self.verify()
        self.assertEqual(code, 1)
        self.assertEqual(report['new_tracked_files_outside_v2'], ['new_engine.py'])

    def test_only_the_exact_new_pages_workflow_is_authorized(self):
        self.redesign()
        folder = self.root / '.github/workflows'
        folder.mkdir(parents=True)
        (folder / 'pages.yml').write_text('name: Documentation website\n')
        subprocess.run(['git', 'add', '.github/workflows/pages.yml'], cwd=self.root, check=True)
        code, report = self.verify()
        self.assertEqual(code, 0)
        self.assertEqual(report['authorized_new_infrastructure'], ['.github/workflows/pages.yml'])
        (folder / 'pages-helper.yml').write_text('name: Unreviewed\n')
        subprocess.run(['git', 'add', '.github/workflows/pages-helper.yml'], cwd=self.root, check=True)
        code, report = self.verify()
        self.assertEqual(code, 1)
        self.assertEqual(report['new_tracked_files_outside_v2'], ['.github/workflows/pages-helper.yml'])

    def test_pages_infrastructure_does_not_exempt_original_hashes(self):
        folder = self.root / '.github/workflows'
        folder.mkdir(parents=True)
        (folder / 'pages.yml').write_text('name: Documentation website\n')
        subprocess.run(['git', 'add', '.github/workflows/pages.yml'], cwd=self.root, check=True)
        (self.root / 'engine.py').write_text('CHANGED = True\n')
        code, report = self.verify()
        self.assertEqual(code, 1)
        self.assertIn({'path': 'engine.py', 'error': 'changed'}, report['problems'])

    def test_generated_report_attributes_are_scoped_to_results(self):
        for name in ('results/.gitattributes',):
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('*.html linguist-generated=true\n')
            subprocess.run(['git', 'add', name], cwd=self.root, check=True)
        code, report = self.verify()
        self.assertEqual(code, 0)
        self.assertEqual(report['authorized_new_infrastructure'],
                         ['results/.gitattributes'])
        (self.root / 'docs/.gitattributes').write_text('* linguist-generated=true\n')
        subprocess.run(['git', 'add', 'docs/.gitattributes'], cwd=self.root, check=True)
        code, report = self.verify()
        self.assertEqual(code, 1)
        self.assertEqual(report['new_tracked_files_outside_v2'], ['docs/.gitattributes'])


if __name__ == '__main__':
    unittest.main()
