from decimal import Decimal

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from .models import Material


User = get_user_model()


class MaterialModelTests(TestCase):
    def test_material_stores_unit_and_price(self):
        material = Material.objects.create(
            name='Vidro temperado 8 mm',
            unit_type=Material.UnitType.SQUARE_METER,
            unit_price=Decimal('245.90'),
        )

        self.assertEqual(str(material), 'Vidro temperado 8 mm')
        self.assertEqual(material.get_unit_type_display(), 'Metro quadrado (m²)')
        self.assertIn(Material, admin.site._registry)

    def test_material_rejects_negative_price(self):
        material = Material(
            name='Material inválido',
            unit_type=Material.UnitType.LINEAR_METER,
            unit_price=Decimal('-0.01'),
        )

        with self.assertRaises(ValidationError):
            material.full_clean()


class CalculatorWorkflowTests(TestCase):
    password = 'Senha-Forte-2026'

    def setUp(self):
        self.staff = User.objects.create_superuser(
            username='calculator-admin',
            email='calculator@example.com',
            password=self.password,
        )
        self.customer = User.objects.create_user(
            username='calculator-customer',
            password=self.password,
        )
        self.material = Material.objects.create(
            name='Perfil de alumínio',
            unit_type=Material.UnitType.LINEAR_METER,
            unit_price=Decimal('82.50'),
        )

    def test_calculator_is_restricted_to_staff(self):
        url = reverse('calculator:home')
        anonymous = self.client.get(url)
        self.assertRedirects(anonymous, f'{reverse("accounts:login")}?next={url}')

        self.client.force_login(self.customer)
        self.assertEqual(self.client.get(url).status_code, 403)

        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(url).status_code, 200)

    def test_calculator_renders_material_data_for_automatic_calculation(self):
        self.client.force_login(self.staff)

        response = self.client.get(reverse('calculator:home'))

        self.assertContains(response, 'Calculadora de serviços')
        self.assertContains(response, 'Perfil de alumínio')
        self.assertContains(response, 'data-unit-type="ML"')
        self.assertContains(response, 'data-unit-price="82.50"')
        self.assertContains(response, 'Metragem linear')
        self.assertContains(response, 'R$ 82,50')

    def test_calculator_has_material_search_and_only_one_create_button(self):
        self.client.force_login(self.staff)

        response = self.client.get(reverse('calculator:home'))

        self.assertContains(response, 'id="material-search"')
        self.assertContains(response, 'Pesquisar material')
        self.assertContains(response, 'Nenhum material encontrado para esta pesquisa.')
        self.assertContains(response, f'data-material-id="{self.material.pk}"')
        self.assertContains(response, f'data-select-material="{self.material.pk}"')
        self.assertContains(response, 'Selecionar Perfil de alumínio para calcular')
        self.assertContains(
            response,
            f'href="{reverse("calculator:material_create")}"',
            count=1,
        )
        self.assertContains(response, 'Novo Material')
        self.assertNotContains(response, '> Adicionar</a>')

    def test_staff_can_create_material_with_comma_decimal(self):
        self.client.force_login(self.staff)

        create_page = self.client.get(reverse('calculator:material_create'))
        self.assertContains(create_page, 'Salvar e adicionar outro')

        response = self.client.post(
            reverse('calculator:material_create'),
            {
                'name': 'Vidro laminado',
                'unit_type': Material.UnitType.SQUARE_METER,
                'unit_price': '315,75',
            },
        )

        self.assertRedirects(response, reverse('calculator:home'))
        created = Material.objects.get(name='Vidro laminado')
        self.assertEqual(created.unit_price, Decimal('315.75'))

    def test_material_name_is_unique_ignoring_case(self):
        self.client.force_login(self.staff)

        response = self.client.post(
            reverse('calculator:material_create'),
            {
                'name': 'perfil de alumínio',
                'unit_type': Material.UnitType.LINEAR_METER,
                'unit_price': '90,00',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Já existe um material com este nome.')
        self.assertEqual(Material.objects.count(), 1)

    def test_staff_can_edit_and_delete_material(self):
        self.client.force_login(self.staff)

        edit_response = self.client.post(
            reverse('calculator:material_edit', args=[self.material.pk]),
            {
                'name': 'Perfil de alumínio reforçado',
                'unit_type': Material.UnitType.LINEAR_METER,
                'unit_price': '95,40',
            },
        )
        self.assertRedirects(edit_response, reverse('calculator:home'))
        self.material.refresh_from_db()
        self.assertEqual(self.material.unit_price, Decimal('95.40'))

        delete_url = reverse('calculator:material_delete', args=[self.material.pk])
        self.assertEqual(self.client.get(delete_url).status_code, 405)
        delete_response = self.client.post(delete_url)
        self.assertRedirects(delete_response, reverse('calculator:home'))
        self.assertFalse(Material.objects.filter(pk=self.material.pk).exists())
