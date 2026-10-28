from decimal import Decimal

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from categories.models import Category

from .models import Product, ProductStockExit


User = get_user_model()


class ProductModelTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name='Vidros')

    def test_product_has_automatic_id_and_optional_presentation_fields(self):
        product = Product.objects.create(
            name='Vidro temperado',
            category=self.category,
            price=Decimal('249.90'),
        )

        self.assertIsNotNone(product.pk)
        self.assertFalse(product.photo)
        self.assertEqual(product.description, '')
        self.assertEqual(product.stock_quantity, 0)
        self.assertTrue(product.show_in_showcase)
        self.assertEqual(str(product), 'Vidro temperado')

    def test_product_rejects_negative_price(self):
        product = Product(
            name='Produto inválido',
            category=self.category,
            price=Decimal('-0.01'),
        )

        with self.assertRaises(ValidationError):
            product.full_clean()

    def test_product_rejects_negative_stock_quantity(self):
        product = Product(
            name='Produto com estoque inválido',
            category=self.category,
            price=Decimal('10.00'),
            stock_quantity=-1,
        )

        with self.assertRaises(ValidationError):
            product.full_clean()


class ProductShowcaseTests(TestCase):
    def setUp(self):
        category = Category.objects.create(name='Ferragens')
        self.product = Product.objects.create(
            name='Puxador inox',
            category=category,
            price=Decimal('89.50'),
            description='Puxador resistente para portas de vidro.',
        )

    def test_catalog_hides_product_price_and_shows_detail_link(self):
        response = self.client.get(reverse('products:list'))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'products/product_list.html')
        self.assertContains(response, 'Puxador inox')
        self.assertNotContains(response, 'R$ 89,50')
        self.assertContains(response, reverse('products:detail', args=[self.product.pk]))
        self.assertNotContains(response, 'Cadastrar produto')

    def test_catalog_paginates_six_products_per_page(self):
        products = [self.product]
        products.extend(
            Product.objects.create(
                name=f'Produto {index:02d}',
                category=self.product.category,
                price=Decimal('10.00') + index,
            )
            for index in range(1, 7)
        )

        first_page = self.client.get(reverse('products:list'))
        second_page = self.client.get(reverse('products:list'), {'page': 2})

        self.assertEqual(len(first_page.context['products']), 6)
        self.assertEqual(len(second_page.context['products']), 1)
        self.assertContains(first_page, 'aria-current="page"')
        self.assertContains(first_page, '?page=2')
        self.assertContains(second_page, products[0].name)
        self.assertNotContains(first_page, products[0].name)

    def test_product_detail_hides_price_and_shows_public_information(self):
        response = self.client.get(reverse('products:detail', args=[self.product.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Puxador inox')
        self.assertContains(response, 'Ferragens')
        self.assertNotContains(response, 'R$ 89,50')
        self.assertContains(response, 'Puxador resistente para portas de vidro.')

    def test_unknown_product_returns_not_found(self):
        response = self.client.get(reverse('products:detail', args=[999999]))

        self.assertEqual(response.status_code, 404)

    def test_hidden_product_is_removed_from_catalog_and_detail(self):
        self.product.show_in_showcase = False
        self.product.save(update_fields=('show_in_showcase',))

        catalog = self.client.get(reverse('products:list'))
        detail = self.client.get(reverse('products:detail', args=[self.product.pk]))

        self.assertNotContains(catalog, self.product.name)
        self.assertEqual(detail.status_code, 404)


class ProductAdminTests(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_superuser(
            username='product-admin',
            email='product-admin@example.com',
            password='Senha-Forte-2026',
        )
        self.category = Category.objects.create(name='Acessórios')

    def test_models_are_available_only_in_separate_admin(self):
        self.assertIn(Product, admin.site._registry)
        self.assertIn(ProductStockExit, admin.site._registry)
        self.assertIn(Category, admin.site._registry)
        self.assertEqual(reverse('admin:index'), '/admin/')

        add_url = reverse('admin:products_product_add')
        anonymous_response = self.client.get(add_url)
        self.assertRedirects(anonymous_response, f'{reverse("admin:login")}?next={add_url}')

    def test_admin_can_register_product_using_existing_category(self):
        self.client.force_login(self.admin_user)

        response = self.client.post(
            reverse('admin:products_product_add'),
            {
                'name': 'Kit para box',
                'category': self.category.pk,
                'price': '159.90',
                'stock_quantity': '7',
                'description': '',
                '_save': 'Salvar',
            },
        )

        self.assertEqual(response.status_code, 302)
        product = Product.objects.get(name='Kit para box')
        self.assertEqual(product.category, self.category)
        self.assertEqual(product.price, Decimal('159.90'))
        self.assertEqual(product.stock_quantity, 7)
