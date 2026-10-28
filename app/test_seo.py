from decimal import Decimal
from xml.etree import ElementTree

from django.test import TestCase, override_settings
from django.urls import reverse

from categories.models import Category
from glazing_services.models import Service
from products.models import Product


PRODUCTION_URL = 'https://comercial-globo-vidracaria-e-construcao.mayezer.com'


@override_settings(PUBLIC_SITE_URL=PRODUCTION_URL)
class PublicSEOTests(TestCase):
    def setUp(self):
        category = Category.objects.create(name='Vidros')
        self.product = Product.objects.create(
            name='Espelho sob medida',
            category=category,
            price=Decimal('100.00'),
            description='Espelho preparado sob medida para diferentes ambientes.',
        )
        self.hidden_product = Product.objects.create(
            name='Produto interno',
            category=category,
            price=Decimal('50.00'),
            show_in_showcase=False,
        )
        self.service = Service.objects.create(
            name='Instalação de box',
            service_type='Instalação',
            description='Instalação profissional de box para banheiro.',
        )
        self.hidden_service = Service.objects.create(
            name='Serviço interno',
            service_type='Manutenção',
            show_in_showcase=False,
        )

    def test_sitemap_has_only_absolute_public_published_urls(self):
        response = self.client.get(reverse('sitemap'))
        root = ElementTree.fromstring(response.content)
        namespace = {'s': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
        locations = {element.text for element in root.findall('s:url/s:loc', namespace)}

        expected = {
            f'{PRODUCTION_URL}/',
            f'{PRODUCTION_URL}{reverse("products:list")}',
            f'{PRODUCTION_URL}{reverse("products:detail", args=[self.product.pk])}',
            f'{PRODUCTION_URL}{reverse("glazing_services:list")}',
            f'{PRODUCTION_URL}{reverse("glazing_services:detail", args=[self.service.pk])}',
        }
        self.assertEqual(response['Content-Type'], 'application/xml')
        self.assertEqual(locations, expected)
        self.assertNotIn(
            f"{PRODUCTION_URL}{reverse('products:detail', args=[self.hidden_product.pk])}",
            locations,
        )
        self.assertNotIn(
            f"{PRODUCTION_URL}{reverse('glazing_services:detail', args=[self.hidden_service.pk])}",
            locations,
        )
        sitemap_text = response.content.decode()
        for private_path in ('/admin/', '/painel/', '/perfil/', '/entrar/', '/criar-conta/'):
            self.assertNotIn(private_path, sitemap_text)

    def test_robots_allows_search_and_points_to_sitemap_while_blocking_private_routes(self):
        response = self.client.get(reverse('robots'))
        text = response.content.decode()

        self.assertEqual(response['Content-Type'], 'text/plain; charset=utf-8')
        self.assertIn('User-agent: *\nAllow: /', text)
        self.assertIn('Disallow: /admin/', text)
        self.assertIn('Disallow: /painel/', text)
        self.assertIn(f'Sitemap: {PRODUCTION_URL}/sitemap.xml', text)

    def test_llms_file_is_short_factual_and_uses_existing_public_contact(self):
        response = self.client.get(reverse('llms'))
        text = response.content.decode()

        self.assertIn('# Globo Vidraçaria e Materiais para Construção', text)
        self.assertIn(self.product.name, text)
        self.assertIn(self.service.name, text)
        self.assertNotIn(self.hidden_product.name, text)
        self.assertNotIn(self.hidden_service.name, text)
        self.assertIn('+55 93 99106-3146', text)
        self.assertLess(len(text), 4000)

    @override_settings(GOOGLE_SITE_VERIFICATION='verification-test-value')
    def test_public_pages_have_canonical_descriptions_open_graph_and_json_ld(self):
        paths = (
            reverse('home'),
            reverse('products:list'),
            reverse('products:detail', args=[self.product.pk]),
            reverse('glazing_services:list'),
            reverse('glazing_services:detail', args=[self.service.pk]),
        )
        descriptions = set()
        for path in paths:
            with self.subTest(path=path):
                response = self.client.get(path)
                html = response.content.decode()
                self.assertIn(f'<link rel="canonical" href="{PRODUCTION_URL}{path}">', html)
                self.assertIn('<meta name="description" content="', html)
                self.assertIn('<meta property="og:title"', html)
                self.assertIn(f'<meta property="og:url" content="{PRODUCTION_URL}{path}">', html)
                self.assertIn('"@type":"LocalBusiness"', html)
                self.assertIn(
                    '<meta name="google-site-verification" content="verification-test-value">',
                    html,
                )
                self.assertNotIn('name="keywords"', html)
                description = html.split('<meta name="description" content="', 1)[1].split('">', 1)[0]
                descriptions.add(description)
        self.assertGreaterEqual(len(descriptions), 4)

    def test_canonical_ignores_query_string(self):
        response = self.client.get(reverse('products:list'), {'page': 2, 'utm_source': 'test'})

        self.assertContains(
            response,
            f'<link rel="canonical" href="{PRODUCTION_URL}{reverse("products:list")}">',
            html=True,
        )
