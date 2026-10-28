from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from categories.models import Category
from products.models import Product


User = get_user_model()


class ShowcaseRoutingTests(TestCase):
    def test_home_uses_home_template_and_background_copy(self):
        response = self.client.get(reverse('home'))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'showcase/home.html')
        self.assertContains(response, 'Vidraçaria, vidros sob medida e materiais para construção')
        self.assertContains(response, 'Com mais de 25 anos de experiência')

    def test_home_has_store_favicon_current_map_link_and_mobile_menu_script(self):
        response = self.client.get(reverse('home'))

        self.assertContains(response, 'rel="icon"')
        self.assertContains(response, 'img/logo_globo')
        self.assertContains(response, 'https://maps.app.goo.gl/Fr7DfghdV6aB5Lj29')
        self.assertContains(response, 'bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js')

    def test_home_displays_only_six_most_recent_products(self):
        category = Category.objects.create(name='Destaques')
        products = [
            Product.objects.create(
                name=f'Produto {index}',
                category=category,
                price=Decimal('10.00') + index,
            )
            for index in range(1, 8)
        ]

        response = self.client.get(reverse('home'))

        self.assertEqual(len(response.context['featured_products']), 6)
        self.assertContains(response, products[-1].name)
        self.assertNotContains(response, products[0].name)

    def test_home_excludes_products_hidden_from_client_showcase(self):
        category = Category.objects.create(name='Internos')
        hidden_product = Product.objects.create(
            name='Produto fora da vitrine',
            category=category,
            price=Decimal('10.00'),
            show_in_showcase=False,
        )

        response = self.client.get(reverse('home'))

        self.assertNotContains(response, hidden_product.name)

    def test_admin_logout_redirects_to_admin_login(self):
        admin_user = User.objects.create_superuser(
            username='admin-routing-test',
            email='admin-routing@example.com',
            password='Senha-Forte-2026',
        )
        self.client.force_login(admin_user)

        response = self.client.post(reverse('admin:logout'))

        self.assertRedirects(response, reverse('admin:login'))
        self.assertNotIn('_auth_user_id', self.client.session)
