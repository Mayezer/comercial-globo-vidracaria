from django.contrib import admin
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Service


User = get_user_model()


class GlazingServicesRenameTests(TestCase):
    def test_python_package_and_url_namespace_use_new_name_without_changing_table(self):
        self.assertEqual(Service._meta.app_config.name, 'glazing_services')
        self.assertEqual(Service._meta.app_config.verbose_name, 'glazing_services')
        self.assertEqual(Service._meta.db_table, 'services_service')
        self.assertEqual(reverse('glazing_services:list'), '/servicos/')


class ServiceModelTests(TestCase):
    def test_service_has_optional_description_and_photo(self):
        service = Service.objects.create(
            name='Instalação de box',
            service_type='Instalação',
        )

        self.assertIsNotNone(service.pk)
        self.assertEqual(service.description, '')
        self.assertFalse(service.photo)
        self.assertTrue(service.show_in_showcase)
        self.assertEqual(str(service), 'Instalação de box')


class ServiceShowcaseTests(TestCase):
    def test_showcase_displays_only_registered_services(self):
        service = Service.objects.create(
            name='Fechamento de sacada',
            service_type='Envidraçamento',
            description='Proteção e conforto para a área externa.',
        )

        response = self.client.get(reverse('glazing_services:list'))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'glazing_services/service_list.html')
        self.assertContains(response, service.name)
        self.assertContains(response, service.service_type)
        self.assertContains(response, service.description)
        self.assertNotContains(response, 'Cadastrar serviço')
        self.assertContains(response, reverse('glazing_services:detail', args=[service.pk]))

        detail = self.client.get(reverse('glazing_services:detail', args=[service.pk]))
        self.assertEqual(detail.status_code, 200)
        self.assertContains(detail, service.name)
        self.assertContains(detail, service.description)

    def test_showcase_paginates_six_services_per_page(self):
        services = [
            Service.objects.create(
                name=f'Serviço {index:02d}',
                service_type='Instalação',
            )
            for index in range(1, 8)
        ]

        first_page = self.client.get(reverse('glazing_services:list'))
        second_page = self.client.get(reverse('glazing_services:list'), {'page': 2})

        self.assertEqual(len(first_page.context['services']), 6)
        self.assertContains(first_page, services[0].name)
        self.assertNotContains(first_page, services[-1].name)
        self.assertContains(first_page, 'aria-current="page"')
        self.assertContains(first_page, '?page=2')
        self.assertEqual(len(second_page.context['services']), 1)
        self.assertContains(second_page, services[-1].name)
        self.assertNotContains(second_page, services[0].name)

    def test_empty_showcase_does_not_render_example_services(self):
        response = self.client.get(reverse('glazing_services:list'))

        self.assertContains(response, 'Serviços em breve')
        self.assertNotContains(response, 'Instalação de box')

    def test_hidden_service_is_removed_from_showcase(self):
        hidden_service = Service.objects.create(
            name='Serviço interno',
            service_type='Manutenção',
            show_in_showcase=False,
        )

        response = self.client.get(reverse('glazing_services:list'))

        self.assertNotContains(response, hidden_service.name)
        self.assertEqual(
            self.client.get(
                reverse('glazing_services:detail', args=[hidden_service.pk])
            ).status_code,
            404,
        )


class ServiceAdminTests(TestCase):
    def test_admin_can_register_service(self):
        admin_user = User.objects.create_superuser(
            username='service-admin',
            email='service-admin@example.com',
            password='Senha-Forte-2026',
        )
        self.client.force_login(admin_user)

        response = self.client.post(
            reverse('admin:services_service_add'),
            {
                'name': 'Manutenção de janela',
                'service_type': 'Manutenção',
                'description': '',
                '_save': 'Salvar',
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(Service.objects.filter(name='Manutenção de janela').exists())
        self.assertIn(Service, admin.site._registry)
