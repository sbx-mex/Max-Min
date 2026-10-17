from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from build_public_site import copy_public


class PublicSiteTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / 'root'; self.root.mkdir()
        self.output = Path(self.temp.name) / 'public'
        for name in ['sw.js', 'manifest.webmanifest']:
            (self.root / name).write_text('{}')
        (self.root / 'index.html').write_text('<script src="js/app.js"></script>')
        (self.root / 'js').mkdir(); (self.root / 'js/app.js').write_text('true')

    def tearDown(self):
        self.temp.cleanup()

    def test_only_public_resources_enter_pages_artifact(self):
        for name in ['sources/private.xlsx', 'updates/incoming/week.csv', 'audit/report.json', 'secret.txt']:
            path = self.root / name; path.parent.mkdir(parents=True, exist_ok=True); path.write_text('private')
        copy_public(self.root, self.output)
        self.assertTrue((self.output / 'js/app.js').is_file())
        self.assertTrue((self.output / '.nojekyll').is_file())
        self.assertFalse((self.output / 'sources').exists())
        self.assertFalse((self.output / 'updates').exists())
        self.assertFalse((self.output / 'audit').exists())
        self.assertFalse((self.output / 'secret.txt').exists())

    def test_missing_referenced_resource_fails(self):
        (self.root / 'js/app.js').unlink()
        with self.assertRaisesRegex(ValueError, 'faltante'):
            copy_public(self.root, self.output)

    def test_symlink_cannot_publish_external_bytes(self):
        (self.root / 'js/external.js').symlink_to(self.root / 'secret.txt')
        with self.assertRaisesRegex(ValueError, 'enlaces'):
            copy_public(self.root, self.output)
