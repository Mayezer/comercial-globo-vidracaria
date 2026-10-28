"""Verifica as barreiras contra exportação e rastreamento de dados locais."""

import base64
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from scripts.check_public_files import is_private_path
from scripts.create_local_env import create_local_env
from scripts import export_public_source


class PublicationSafetyTests(unittest.TestCase):
    def test_local_keys_are_independent_and_file_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            first = Path(directory) / '.env'
            second = Path(directory) / '.env.other'
            create_local_env(first)
            create_local_env(second)
            original = first.read_bytes()
            with self.assertRaises(FileExistsError):
                create_local_env(first)
            self.assertEqual(first.read_bytes(), original)
            values = dict(
                line.split('=', 1) for line in original.decode().splitlines()
                if line and not line.startswith('#')
            )
            encryption = values['FIELD_ENCRYPTION_KEYS'].split(':', 1)[1]
            hashing = values['FIELD_HASH_KEY']
            self.assertEqual(len(base64.urlsafe_b64decode(encryption)), 32)
            self.assertEqual(len(base64.urlsafe_b64decode(hashing)), 32)
            self.assertNotEqual(encryption, hashing)
            self.assertNotEqual(first.read_bytes(), second.read_bytes())
            self.assertEqual(values['SQLITE_NAME'], 'demo.sqlite3')
            self.assertEqual(values['DATABASE_URL'], '')
            self.assertEqual(values['EMAIL_DELIVERY_ENABLED'], 'False')

    def test_tracked_data_is_rejected_even_in_nested_paths(self):
        for name in (
            '.env', '.env.production', 'app/.env.example', 'media/photo.jpg',
            'app/uploads/customer.py', 'db.sqlite3', 'demo.sqlite3-wal',
            'db.sqlite3-journal', 'backup.dump', 'logs/server.log', 'key.pem',
            'app/credentials.json', 'node_modules/example/index.js',
        ):
            with self.subTest(name=name):
                self.assertTrue(is_private_path(name))
        for name in ('.env.example', 'app/settings.py', '.github/workflows/secret-scanning.yml'):
            with self.subTest(name=name):
                self.assertFalse(is_private_path(name))

    def test_export_preserves_the_sitemap_template(self):
        included = {path.relative_to(export_public_source.ROOT).as_posix()
                    for path in export_public_source.source_files()}
        self.assertIn('templates/seo/sitemap.xml', included)

    def test_archive_excludes_nested_data_and_unapproved_images(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'README.md').write_text('example')
            for name in (
                'app/settings.py', 'app/media/private.py', 'app/.env',
                'app/local.sqlite3', 'app/avatar.jpg', 'app/__pycache__/cached.py',
            ):
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('example')
            with (
                patch.object(export_public_source, 'ROOT', root),
                patch.object(export_public_source, 'ROOT_FILES', ('README.md',)),
                patch.object(export_public_source, 'SOURCE_DIRS', ('app',)),
            ):
                output = root / 'output.zip'
                export_public_source.export_source(output)
                with zipfile.ZipFile(output) as archive:
                    self.assertEqual(set(archive.namelist()), {
                        'globo-vidracaria/README.md', 'globo-vidracaria/app/settings.py',
                    })
                with self.assertRaises(FileExistsError):
                    export_public_source.export_source(output)

    def test_export_rejects_symlinks_to_outside_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'app').mkdir()
            (root / 'outside.py').write_text('private')
            (root / 'app' / 'leak.py').symlink_to(root / 'outside.py')
            with (
                patch.object(export_public_source, 'ROOT', root),
                patch.object(export_public_source, 'ROOT_FILES', ()),
                patch.object(export_public_source, 'SOURCE_DIRS', ('app',)),
                self.assertRaises(ValueError),
            ):
                export_public_source.source_files()


if __name__ == '__main__':
    unittest.main()
