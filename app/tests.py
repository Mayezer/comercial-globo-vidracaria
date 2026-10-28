from django.test import TestCase, override_settings


@override_settings(
    DEBUG=False,
    SECURE_HSTS_SECONDS=31536000,
    SECURE_HSTS_INCLUDE_SUBDOMAINS=True,
    SECURE_HSTS_PRELOAD=True,
)
class ProductionSecurityHeadersTests(TestCase):
    def test_secure_home_response_has_browser_protections(self):
        response = self.client.get('/', secure=True)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers['X-Frame-Options'], 'DENY')
        self.assertEqual(response.headers['X-Content-Type-Options'], 'nosniff')
        self.assertEqual(response.headers['Referrer-Policy'], 'same-origin')
        self.assertEqual(response.headers['Cross-Origin-Opener-Policy'], 'same-origin')
        self.assertEqual(response.headers['Cross-Origin-Resource-Policy'], 'same-origin')
        self.assertIn("default-src 'self'", response.headers['Content-Security-Policy'])
        self.assertIn("frame-ancestors 'none'", response.headers['Content-Security-Policy'])
        self.assertIn(
            "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net",
            response.headers['Content-Security-Policy'],
        )
        self.assertIn('camera=()', response.headers['Permissions-Policy'])
        self.assertEqual(
            response.headers['Strict-Transport-Security'],
            'max-age=31536000; includeSubDomains; preload',
        )


@override_settings(
    DEBUG=False,
    STORAGES={
        'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
        'staticfiles': {
            'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage',
        },
    },
)
class FriendlyNotFoundPageTests(TestCase):
    def test_unknown_public_url_uses_friendly_404_page(self):
        response = self.client.get('/pagina-que-nao-existe/', secure=True)

        self.assertEqual(response.status_code, 404)
        self.assertTemplateUsed(response, '404.html')
        self.assertContains(response, 'Não encontramos esta página.', status_code=404)
        self.assertContains(response, 'Voltar ao início', status_code=404)
        self.assertContains(response, 'Ver produtos', status_code=404)
        self.assertContains(response, 'Conhecer serviços', status_code=404)
        self.assertContains(response, 'noindex, nofollow', status_code=404)
