"""Configuração de produção deve recusar banco sem senha explícita."""

from pathlib import Path
import runpy
import secrets
from unittest.mock import patch

from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase


class ProductionDatabaseSettingsTests(SimpleTestCase):
    def load_settings(self, **database_environment):
        environment = {
            'DJANGO_DEBUG': 'False',
            'DJANGO_SECRET_KEY': secrets.token_urlsafe(50),
            'FIELD_ENCRYPTION_KEYS': 'v1:' + secrets.token_urlsafe(32),
            'FIELD_HASH_KEY': secrets.token_urlsafe(32),
            **database_environment,
        }
        with patch.dict('os.environ', environment, clear=True):
            return runpy.run_path(str(Path(__file__).with_name('settings.py')))

    def test_production_rejects_missing_postgres_password(self):
        with self.assertRaisesMessage(ImproperlyConfigured, 'Defina POSTGRES_PASSWORD'):
            self.load_settings()

    def test_production_uses_explicit_postgres_password(self):
        password = secrets.token_urlsafe(32)
        configuration = self.load_settings(POSTGRES_PASSWORD=password)
        self.assertEqual(configuration['DATABASES']['default']['PASSWORD'], password)

    def test_development_has_no_builtin_postgres_password(self):
        configuration = self.load_settings(DJANGO_DEBUG='True')
        self.assertEqual(configuration['DATABASES']['default']['PASSWORD'], '')
