from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from accounts.models import Profile
from categories.models import Category
from products.models import Product, ProductStockExit
from glazing_services.models import Service
from app.crypto import blind_index

from .models import (
    CashTransaction,
    Employee,
    Expense,
    Payroll,
    QuoteAdminNotification,
    QuoteRequest,
    QuoteStatusHistory,
    Supplier,
    SystemSettings,
)


User = get_user_model()


class DashboardWorkflowTests(TestCase):
    password = 'Senha-Forte-2026'

    def setUp(self):
        self.admin_user = User.objects.create_superuser(
            username='gestor',
            email='gestor@example.com',
            password=self.password,
        )
        self.customer_user = User.objects.create_user(
            username='52998224725',
            email='cliente@example.com',
            password=self.password,
        )
        self.customer = Profile.objects.create(
            user=self.customer_user,
            account_type=Profile.AccountType.INDIVIDUAL,
            document='52998224725',
            email='cliente@example.com',
            full_name='Maria Cliente',
        )
        self.category = Category.objects.create(name='Vidros')
        self.product = Product.objects.create(
            name='Vidro temperado',
            category=self.category,
            price=Decimal('200.00'),
            stock_quantity=10,
        )
        self.service = Service.objects.create(
            name='Instalação de box',
            service_type='Instalação',
        )

    def complete_address(self):
        self.customer.street = 'Rua das Flores'
        self.customer.neighborhood = 'Centro'
        self.customer.house_number = '25'
        self.customer.reference_point = 'Próximo à praça'
        self.customer.phone = '93999999999'
        self.customer.save()

    def create_quote(self):
        self.complete_address()
        quote = QuoteRequest(details='Box para banheiro')
        quote.copy_customer_data(self.customer)
        quote.save()
        quote.products.add(self.product)
        return quote

    def test_custom_panel_is_restricted_to_staff(self):
        panel_url = reverse('dashboard:home')
        anonymous_response = self.client.get(panel_url)
        self.assertRedirects(
            anonymous_response,
            f'{reverse("accounts:login")}?next={panel_url}',
        )

        self.client.force_login(self.customer_user)
        self.assertEqual(self.client.get(panel_url).status_code, 403)

        self.client.force_login(self.admin_user)
        response = self.client.get(panel_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Visão geral')
        self.assertContains(response, 'Orçamentos')
        self.assertContains(response, 'Clientes')

    def test_hamburger_menu_groups_related_features_and_opens_current_section(self):
        self.client.force_login(self.admin_user)

        home_response = self.client.get(reverse('dashboard:home'))
        home_html = home_response.content.decode()

        self.assertContains(home_response, 'data-sidebar-open')
        self.assertContains(home_response, 'Atendimento')
        self.assertContains(home_response, 'Catálogo e estoque')
        self.assertContains(home_response, 'Financeiro')
        self.assertContains(home_response, 'Equipe e administração')
        self.assertEqual(home_html.count('class="sidebar-group"'), 4)

        finance_response = self.client.get(reverse('dashboard:monthly_finance'))
        finance_html = finance_response.content.decode()

        finance_group_start = finance_html.index('<summary class="sidebar-group-summary"><i class="bi bi-graph-up-arrow"></i> Financeiro')
        finance_details_start = finance_html.rfind('<details', 0, finance_group_start)
        finance_details_tag = finance_html[finance_details_start:finance_html.index('>', finance_details_start) + 1]
        self.assertEqual(finance_details_tag, '<details class="sidebar-group active" open>')
        self.assertContains(finance_response, 'Caixa diário')
        self.assertContains(finance_response, 'Faturamento mensal')

    def test_only_superuser_can_open_administrator_management(self):
        list_url = reverse('dashboard:administrator_list')
        create_url = reverse('dashboard:administrator_create')

        anonymous_response = self.client.get(list_url)
        self.assertRedirects(
            anonymous_response,
            f'{reverse("accounts:login")}?next={list_url}',
        )

        regular_admin = User.objects.create_user(
            username='operador',
            email='operador@example.com',
            password=self.password,
            is_staff=True,
        )
        self.client.force_login(regular_admin)
        self.assertEqual(self.client.get(list_url).status_code, 403)
        self.assertEqual(self.client.get(create_url).status_code, 403)

        self.client.force_login(self.admin_user)
        response = self.client.get(list_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Novo administrador')
        self.assertContains(response, self.admin_user.email)

    def test_superuser_can_create_staff_administrator(self):
        self.client.force_login(self.admin_user)

        response = self.client.post(
            reverse('dashboard:administrator_create'),
            {
                'first_name': 'Ana',
                'last_name': 'Operadora',
                'username': 'ana.operadora',
                'email': 'ANA@EXAMPLE.COM',
                'password': self.password,
                'password_confirmation': self.password,
            },
        )

        self.assertRedirects(response, reverse('dashboard:administrator_list'))
        administrator = User.objects.get(username='ana.operadora')
        self.assertEqual(administrator.email, 'ana@example.com')
        self.assertEqual(administrator.get_full_name(), 'Ana Operadora')
        self.assertTrue(administrator.is_active)
        self.assertTrue(administrator.is_staff)
        self.assertFalse(administrator.is_superuser)
        self.assertTrue(administrator.check_password(self.password))

    def test_administrator_creation_rejects_duplicate_email_and_password_mismatch(self):
        self.client.force_login(self.admin_user)
        create_url = reverse('dashboard:administrator_create')

        duplicate_response = self.client.post(
            create_url,
            {
                'username': 'outro-admin',
                'email': self.admin_user.email.upper(),
                'password': self.password,
                'password_confirmation': self.password,
            },
        )
        mismatch_response = self.client.post(
            create_url,
            {
                'username': 'senha-diferente',
                'email': 'senha-diferente@example.com',
                'password': self.password,
                'password_confirmation': 'Senha-Diferente-2026',
            },
        )

        self.assertContains(duplicate_response, 'Já existe uma conta com este e-mail.')
        self.assertContains(mismatch_response, 'As senhas não coincidem.')
        self.assertFalse(User.objects.filter(username__in=['outro-admin', 'senha-diferente']).exists())

    def test_old_admin_panel_url_redirects_to_custom_panel(self):
        response_without_slash = self.client.get('/admin/painel')
        response_with_slash = self.client.get('/admin/painel/')

        self.assertRedirects(
            response_without_slash,
            reverse('dashboard:home'),
            fetch_redirect_response=False,
        )
        self.assertRedirects(
            response_with_slash,
            reverse('dashboard:home'),
            fetch_redirect_response=False,
        )

        self.client.force_login(self.admin_user)
        django_admin = self.client.get(reverse('admin:index'))
        self.assertContains(django_admin, f'href="{reverse("dashboard:home")}"')

    def test_customer_without_address_is_sent_to_complete_profile(self):
        self.client.force_login(self.customer_user)

        response = self.client.get(reverse('dashboard:request_quote'))

        self.assertRedirects(
            response,
            f'{reverse("accounts:edit_profile")}?next=quote',
            fetch_redirect_response=False,
        )

    def test_customer_can_request_only_once_every_four_hours(self):
        self.complete_address()
        self.client.force_login(self.customer_user)
        request_url = reverse('dashboard:request_quote')
        data = {
            'products': [self.product.pk],
            'services': [self.service.pk],
            'details': 'Preciso de medidas e instalação.',
        }

        first_response = self.client.post(request_url, data)
        second_response = self.client.post(request_url, data)

        self.assertRedirects(first_response, request_url)
        self.assertRedirects(second_response, request_url)
        self.assertEqual(QuoteRequest.objects.count(), 1)
        quote = QuoteRequest.objects.get()
        self.assertEqual(quote.customer_name, 'Maria Cliente')
        self.assertEqual(quote.full_address, 'Rua das Flores, nº 25 — Centro (Próximo à praça)')
        self.assertEqual(list(quote.products.all()), [self.product])
        self.assertEqual(list(quote.services.all()), [self.service])

        page = self.client.get(request_url)
        self.assertContains(page, 'Aguarde para solicitar novamente')
        self.assertContains(page, 'disabled')

    def test_customer_quote_only_lists_items_selected_for_showcase(self):
        self.complete_address()
        self.product.show_in_showcase = False
        self.product.save(update_fields=('show_in_showcase',))
        self.service.show_in_showcase = False
        self.service.save(update_fields=('show_in_showcase',))
        self.client.force_login(self.customer_user)

        page = self.client.get(reverse('dashboard:request_quote'))

        self.assertNotContains(page, self.product.name)
        self.assertNotContains(page, self.service.name)

    def test_admin_can_choose_product_and_service_showcase_visibility(self):
        self.client.force_login(self.admin_user)

        product_response = self.client.post(
            reverse('dashboard:product_edit', args=[self.product.pk]),
            {
                'name': self.product.name,
                'category': self.category.pk,
                'new_category': '',
                'price': '200.00',
                'stock_quantity': '10',
                'description': '',
            },
        )
        service_response = self.client.post(
            reverse('dashboard:service_edit', args=[self.service.pk]),
            {
                'name': self.service.name,
                'service_type': self.service.service_type,
                'description': '',
            },
        )

        self.assertRedirects(product_response, reverse('dashboard:product_list'))
        self.assertRedirects(service_response, reverse('dashboard:service_list'))
        self.product.refresh_from_db()
        self.service.refresh_from_db()
        self.assertFalse(self.product.show_in_showcase)
        self.assertFalse(self.service.show_in_showcase)
        self.assertContains(self.client.get(reverse('dashboard:product_list')), 'Oculto')
        self.assertContains(self.client.get(reverse('dashboard:service_list')), 'Oculto')

    def test_status_click_records_admin_and_time(self):
        quote = self.create_quote()
        self.client.force_login(self.admin_user)

        response = self.client.post(
            reverse('dashboard:update_quote_status', args=[quote.pk]),
            {'status': QuoteRequest.Status.COMPLETED},
        )

        self.assertRedirects(response, reverse('dashboard:quote_detail', args=[quote.pk]))
        quote.refresh_from_db()
        action = QuoteStatusHistory.objects.get(quote=quote)
        self.assertEqual(quote.status, QuoteRequest.Status.COMPLETED)
        self.assertEqual(quote.status_updated_by, self.admin_user)
        self.assertIsNotNone(quote.status_updated_at)
        self.assertEqual(action.admin, self.admin_user)
        self.assertIsNotNone(action.changed_at)

        detail = self.client.get(reverse('dashboard:quote_detail', args=[quote.pk]))
        self.assertContains(detail, 'Maria Cliente')
        self.assertContains(detail, 'WhatsApp do cliente')
        self.assertContains(detail, self.admin_user.username)

    def test_each_admin_receives_popup_notification_once(self):
        quote = self.create_quote()
        endpoint = reverse('dashboard:next_quote_notification')
        self.client.force_login(self.admin_user)

        first_response = self.client.post(endpoint)
        second_response = self.client.post(endpoint)

        self.assertEqual(first_response.json()['quote']['id'], quote.pk)
        self.assertIsNone(second_response.json()['quote'])
        self.assertEqual(
            QuoteAdminNotification.objects.filter(quote=quote, admin=self.admin_user).count(),
            1,
        )

    def test_quote_notification_json_requires_staff_and_minimizes_fields(self):
        quote = self.create_quote()
        endpoint = reverse('dashboard:next_quote_notification')

        anonymous = self.client.post(endpoint)
        self.assertRedirects(
            anonymous,
            f'{reverse("accounts:login")}?next={endpoint}',
        )

        self.client.force_login(self.customer_user)
        self.assertEqual(self.client.post(endpoint).status_code, 403)

        self.client.force_login(self.admin_user)
        response = self.client.post(endpoint)
        payload = response.json()['quote']
        self.assertEqual(set(payload), {'id', 'customer', 'requested_at', 'url'})
        serialized = response.content.decode()
        self.assertNotIn(quote.customer_document, serialized)
        self.assertNotIn(quote.customer_email, serialized)
        self.assertNotIn(quote.customer_phone, serialized)
        self.assertNotIn(quote.customer_street, serialized)

    def test_admin_can_manage_catalog_and_customer_data(self):
        self.client.force_login(self.admin_user)

        product_response = self.client.post(
            reverse('dashboard:product_create'),
            {
                'name': 'Espelho bisotado',
                'new_category': 'Espelhos',
                'price': '350.00',
                'stock_quantity': '8',
                'description': 'Sob medida',
            },
        )
        service_response = self.client.post(
            reverse('dashboard:service_create'),
            {
                'name': 'Troca de roldana',
                'service_type': 'Manutenção',
                'description': 'Manutenção preventiva',
            },
        )
        customer_response = self.client.post(
            reverse('dashboard:customer_edit', args=[self.customer.pk]),
            {
                'account_type': 'PF',
                'document': '529.982.247-25',
                'email': 'novo-email@example.com',
                'full_name': 'Maria Atualizada',
                'corporate_name': '',
                'street': 'Rua Nova',
                'neighborhood': 'Centro',
                'house_number': '80',
                'reference_point': '',
                'phone': '93999999999',
                'is_active': 'on',
            },
        )

        self.assertRedirects(product_response, reverse('dashboard:product_list'))
        self.assertRedirects(service_response, reverse('dashboard:service_list'))
        self.assertRedirects(customer_response, reverse('dashboard:customer_list'))
        self.assertTrue(
            Product.objects.filter(
                name='Espelho bisotado',
                category__name='Espelhos',
                stock_quantity=8,
            ).exists()
        )
        self.assertTrue(Service.objects.filter(name='Troca de roldana').exists())
        self.customer.refresh_from_db()
        self.customer.user.refresh_from_db()
        self.assertEqual(self.customer.full_name, 'Maria Atualizada')
        self.assertEqual(self.customer.email, 'novo-email@example.com')
        self.assertEqual(self.customer.user.email, '')
        self.assertNotEqual(self.customer.user.username, self.customer.document)

    def test_superuser_can_edit_administrator_information_and_password(self):
        administrator = User.objects.create_user(
            username='operador-antigo',
            email='antigo@example.com',
            password=self.password,
            is_staff=True,
        )
        self.client.force_login(self.admin_user)

        edit_page = self.client.get(
            reverse('dashboard:administrator_edit', args=[administrator.pk])
        )
        self.assertContains(edit_page, 'Editar administrador')

        response = self.client.post(
            reverse('dashboard:administrator_edit', args=[administrator.pk]),
            {
                'first_name': 'João',
                'last_name': 'Operador',
                'username': 'joao.operador',
                'email': 'JOAO@EXAMPLE.COM',
                'is_active': 'on',
                'password': 'Nova-Senha-Forte-2026',
                'password_confirmation': 'Nova-Senha-Forte-2026',
            },
        )

        self.assertRedirects(response, reverse('dashboard:administrator_list'))
        administrator.refresh_from_db()
        self.assertEqual(administrator.get_full_name(), 'João Operador')
        self.assertEqual(administrator.email, 'joao@example.com')
        self.assertTrue(administrator.is_staff)
        self.assertTrue(administrator.check_password('Nova-Senha-Forte-2026'))

    def test_catalog_supports_categories_deletion_and_save_another(self):
        self.client.force_login(self.admin_user)

        self.assertContains(
            self.client.get(reverse('dashboard:product_create')),
            'Salvar e adicionar outro',
        )
        self.assertContains(
            self.client.get(reverse('dashboard:service_create')),
            'Salvar e adicionar outro',
        )

        category_response = self.client.post(
            reverse('dashboard:product_list'),
            {'name': 'Espelhos decorativos'},
        )
        product_response = self.client.post(
            reverse('dashboard:product_create'),
            {
                'name': 'Espelho redondo',
                'category': self.category.pk,
                'price': '180.00',
                'stock_quantity': '4',
                'description': '',
                'save_and_add_another': '1',
            },
        )
        service_response = self.client.post(
            reverse('dashboard:service_create'),
            {
                'name': 'Instalação expressa',
                'service_type': 'Instalação',
                'description': '',
                'save_and_add_another': '1',
            },
        )

        self.assertRedirects(category_response, reverse('dashboard:product_list'))
        self.assertTrue(Category.objects.filter(name='Espelhos decorativos').exists())
        self.assertRedirects(product_response, reverse('dashboard:product_create'))
        self.assertRedirects(service_response, reverse('dashboard:service_create'))

        product = Product.objects.get(name='Espelho redondo')
        service = Service.objects.get(name='Instalação expressa')
        self.assertRedirects(
            self.client.post(reverse('dashboard:product_delete', args=[product.pk])),
            reverse('dashboard:product_list'),
        )
        self.assertRedirects(
            self.client.post(reverse('dashboard:service_delete', args=[service.pk])),
            reverse('dashboard:service_list'),
        )
        self.assertFalse(Product.objects.filter(pk=product.pk).exists())
        self.assertFalse(Service.objects.filter(pk=service.pk).exists())

    def test_stock_exit_page_is_restricted_to_staff(self):
        url = reverse('dashboard:product_stock_exit')
        anonymous = self.client.get(url)
        self.assertRedirects(anonymous, f'{reverse("accounts:login")}?next={url}')

        self.client.force_login(self.customer_user)
        self.assertEqual(self.client.get(url).status_code, 403)

        self.client.force_login(self.admin_user)
        page = self.client.get(url)
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, 'Saída de produtos')
        self.assertContains(page, 'Quantidade da saída')
        self.assertContains(page, '10 em estoque')

    def test_admin_can_register_stock_exit_and_update_product_balance(self):
        self.client.force_login(self.admin_user)

        response = self.client.post(
            reverse('dashboard:product_stock_exit'),
            {
                'product': self.product.pk,
                'quantity': '4',
                'notes': 'Instalação do orçamento 152',
            },
        )

        self.assertRedirects(response, reverse('dashboard:product_stock_exit'))
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 6)
        stock_exit = ProductStockExit.objects.get()
        self.assertEqual(stock_exit.product, self.product)
        self.assertEqual(stock_exit.product_name, self.product.name)
        self.assertEqual(stock_exit.quantity, 4)
        self.assertEqual(stock_exit.stock_before, 10)
        self.assertEqual(stock_exit.stock_after, 6)
        self.assertEqual(stock_exit.created_by, self.admin_user)

        page = self.client.get(reverse('dashboard:product_stock_exit'))
        self.assertContains(page, 'Instalação do orçamento 152')
        self.assertContains(page, '10 → 6')

    def test_stock_exit_rejects_quantity_above_available_stock(self):
        self.client.force_login(self.admin_user)

        response = self.client.post(
            reverse('dashboard:product_stock_exit'),
            {
                'product': self.product.pk,
                'quantity': '11',
                'notes': '',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Estoque insuficiente. Há 10 unidade(s) disponível(is).')
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 10)
        self.assertFalse(ProductStockExit.objects.exists())

    def test_cash_daily_and_monthly_pdf_share_the_same_transactions(self):
        self.client.force_login(self.admin_user)
        create_url = reverse('dashboard:cash_transaction_create')

        income_response = self.client.post(
            create_url,
            {
                'transaction_date': '2026-08-25',
                'kind': CashTransaction.Kind.INCOME,
                'description': 'Pagamento de box',
                'amount': '1.250,50',
                'payment_method': CashTransaction.PaymentMethod.PIX,
                'notes': '',
            },
        )
        expense_response = self.client.post(
            create_url,
            {
                'transaction_date': '2026-08-25',
                'kind': CashTransaction.Kind.EXPENSE,
                'description': 'Compra de ferragens',
                'amount': '250,25',
                'payment_method': CashTransaction.PaymentMethod.DEBIT_CARD,
                'notes': 'Fornecedor local',
            },
        )

        daily_url = f'{reverse("dashboard:cash_daily")}?date=2026-08-25'
        self.assertRedirects(income_response, daily_url)
        self.assertRedirects(expense_response, daily_url)
        daily = self.client.get(daily_url)
        self.assertEqual(daily.context['income_total'], Decimal('1250.50'))
        self.assertEqual(daily.context['expense_total'], Decimal('250.25'))
        self.assertEqual(daily.context['balance'], Decimal('1000.25'))
        self.assertContains(daily, 'Pagamento de box')
        self.assertContains(daily, 'Cartão de débito')

        monthly = self.client.get(reverse('dashboard:monthly_finance'), {'month': '2026-08'})
        self.assertEqual(monthly.context['balance'], Decimal('1000.25'))
        pdf = self.client.get(reverse('dashboard:monthly_finance_pdf'), {'month': '2026-08'})
        self.assertEqual(pdf.status_code, 200)
        self.assertEqual(pdf['Content-Type'], 'application/pdf')
        self.assertIn('faturamento-2026-08.pdf', pdf['Content-Disposition'])
        self.assertTrue(pdf.content.startswith(b'%PDF-1.4'))
        self.assertIn('Pagamento de box'.encode('cp1252'), pdf.content)

    def test_admin_can_create_edit_and_delete_employee(self):
        self.client.force_login(self.admin_user)

        self.assertContains(
            self.client.get(reverse('dashboard:employee_create')),
            'Salvar e adicionar outro',
        )

        create_response = self.client.post(
            reverse('dashboard:employee_create'),
            {
                'full_name': 'Carlos da Silva',
                'cpf': '111.444.777-35',
                'monthly_salary': '2.850,00',
            },
        )

        self.assertRedirects(create_response, reverse('dashboard:employee_list'))
        employee = Employee.objects.get(
            cpf_hash=blind_index('11144477735', 'employee.cpf')
        )
        self.assertEqual(employee.monthly_salary, Decimal('2850.00'))
        self.assertEqual(employee.formatted_cpf, '111.444.777-35')

        edit_response = self.client.post(
            reverse('dashboard:employee_edit', args=[employee.pk]),
            {
                'full_name': 'Carlos Silva',
                'cpf': '111.444.777-35',
                'monthly_salary': '3.000,00',
            },
        )
        self.assertRedirects(edit_response, reverse('dashboard:employee_list'))
        employee.refresh_from_db()
        self.assertEqual(employee.full_name, 'Carlos Silva')
        self.assertEqual(employee.monthly_salary, Decimal('3000.00'))

        delete_response = self.client.post(
            reverse('dashboard:employee_delete', args=[employee.pk]),
        )
        self.assertRedirects(delete_response, reverse('dashboard:employee_list'))
        self.assertFalse(Employee.objects.filter(pk=employee.pk).exists())

    def test_profit_calculator_is_available_to_staff(self):
        url = reverse('dashboard:profit_calculator')
        self.client.force_login(self.admin_user)

        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Cálculo de lucro')
        self.assertContains(response, 'type="range"')
        self.assertContains(response, '--range-progress')
        self.assertContains(response, 'Preço sugerido de venda')

    def test_expense_is_synchronized_with_monthly_finance(self):
        self.client.force_login(self.admin_user)
        supplier = Supplier.objects.create(name='Distribuidora de Vidros')

        create_response = self.client.post(
            reverse('dashboard:expense_create'),
            {
                'expense_date': '2026-08-10',
                'category': Expense.Category.ENERGY,
                'description': 'Conta de energia',
                'amount': '480,75',
                'payment_method': CashTransaction.PaymentMethod.PIX,
                'supplier': supplier.pk,
                'notes': 'Oficina',
            },
        )

        expense = Expense.objects.get()
        self.assertRedirects(
            create_response,
            f'{reverse("dashboard:expense_list")}?month=2026-08',
        )
        self.assertIsNotNone(expense.cash_transaction)
        self.assertEqual(expense.cash_transaction.kind, CashTransaction.Kind.EXPENSE)
        self.assertEqual(expense.cash_transaction.amount, Decimal('480.75'))
        self.assertIn(supplier.name, expense.cash_transaction.notes)

        monthly = self.client.get(reverse('dashboard:monthly_finance'), {'month': '2026-08'})
        self.assertEqual(monthly.context['expense_total'], Decimal('480.75'))
        self.assertContains(monthly, 'Conta de energia')

        update_response = self.client.post(
            reverse('dashboard:expense_edit', args=[expense.pk]),
            {
                'expense_date': '2026-08-11',
                'category': Expense.Category.INTERNET,
                'description': 'Internet empresarial',
                'amount': '199,90',
                'payment_method': CashTransaction.PaymentMethod.DEBIT_CARD,
                'supplier': '',
                'notes': '',
            },
        )
        self.assertRedirects(
            update_response,
            f'{reverse("dashboard:expense_list")}?month=2026-08',
        )
        expense.refresh_from_db()
        expense.cash_transaction.refresh_from_db()
        self.assertEqual(expense.cash_transaction.amount, Decimal('199.90'))
        self.assertIn('Internet empresarial', expense.cash_transaction.description)

        cash_transaction_id = expense.cash_transaction_id
        delete_response = self.client.post(reverse('dashboard:expense_delete', args=[expense.pk]))
        self.assertRedirects(
            delete_response,
            f'{reverse("dashboard:expense_list")}?month=2026-08',
        )
        self.assertFalse(Expense.objects.exists())
        self.assertFalse(CashTransaction.objects.filter(pk=cash_transaction_id).exists())

    def test_payroll_quick_creation_generates_pdf_and_finance_expense(self):
        employee = Employee.objects.create(
            full_name='Carlos da Silva',
            cpf='11144477735',
            monthly_salary=Decimal('2850.00'),
        )
        SystemSettings.objects.create(
            company_name='Globo Vidraçaria e Construção',
            tax_id='11222333000181',
            financial_manager='Ana Financeiro',
        )
        self.client.force_login(self.admin_user)

        response = self.client.post(
            reverse('dashboard:payroll_quick_create', args=[employee.pk]),
            {'month': '2026-08'},
        )

        self.assertRedirects(
            response,
            f'{reverse("dashboard:payroll_list")}?month=2026-08',
        )
        payroll = Payroll.objects.get(employee=employee)
        self.assertEqual(payroll.competence.isoformat(), '2026-08-01')
        self.assertEqual(payroll.employee_name, employee.full_name)
        self.assertEqual(payroll.employee_cpf, employee.cpf)
        self.assertEqual(payroll.net_salary, Decimal('2850.00'))
        self.assertEqual(payroll.cash_transaction.amount, Decimal('2850.00'))
        self.assertEqual(payroll.cash_transaction.transaction_date.isoformat(), '2026-08-31')

        monthly = self.client.get(reverse('dashboard:monthly_finance'), {'month': '2026-08'})
        self.assertEqual(monthly.context['expense_total'], Decimal('2850.00'))
        pdf = self.client.get(reverse('dashboard:payroll_pdf', args=[payroll.pk]))
        self.assertEqual(pdf.status_code, 200)
        self.assertEqual(pdf['Content-Type'], 'application/pdf')
        self.assertIn('inline; filename="folha-', pdf['Content-Disposition'])
        self.assertIn('Carlos da Silva'.encode('cp1252'), pdf.content)
        self.assertIn('Assinatura do funcionário'.encode('cp1252'), pdf.content)
        self.assertIn('Ana Financeiro'.encode('cp1252'), pdf.content)

    def test_payroll_edit_updates_linked_finance_transaction(self):
        employee = Employee.objects.create(
            full_name='Carlos da Silva',
            cpf='11144477735',
            monthly_salary=Decimal('2850.00'),
        )
        self.client.force_login(self.admin_user)
        self.client.post(
            reverse('dashboard:payroll_quick_create', args=[employee.pk]),
            {'month': '2026-08'},
        )
        payroll = Payroll.objects.get(employee=employee)

        response = self.client.post(
            reverse('dashboard:payroll_edit', args=[payroll.pk]),
            {
                'employee': employee.pk,
                'competence': '2026-08',
                'gross_salary': '2.850,00',
                'additions': '300,00',
                'deductions': '150,00',
                'payment_date': '2026-08-30',
                'payment_method': CashTransaction.PaymentMethod.PIX,
                'notes': 'Adicional de plantão',
            },
        )

        self.assertRedirects(
            response,
            f'{reverse("dashboard:payroll_list")}?month=2026-08',
        )
        payroll.refresh_from_db()
        payroll.cash_transaction.refresh_from_db()
        self.assertEqual(payroll.net_salary, Decimal('3000.00'))
        self.assertEqual(payroll.cash_transaction.amount, Decimal('3000.00'))
        self.assertEqual(payroll.cash_transaction.transaction_date.isoformat(), '2026-08-30')

    def test_supplier_and_system_settings_can_be_managed(self):
        self.client.force_login(self.admin_user)

        supplier_response = self.client.post(
            reverse('dashboard:supplier_create'),
            {
                'name': 'Vidros Norte',
                'contact_name': 'João',
                'tax_id': '11.222.333/0001-81',
                'phone': '93999999999',
                'email': 'contato@example.com',
                'address': 'Rua Um, 10',
                'is_active': 'on',
                'notes': '',
            },
        )
        settings_response = self.client.post(
            reverse('dashboard:system_settings'),
            {
                'company_name': 'Globo Vidraçaria e Construção',
                'tax_id': '11.222.333/0001-81',
                'phone': '93999999999',
                'email': 'financeiro@example.com',
                'address': 'Avenida Principal, 100',
                'financial_manager': 'Ana Financeiro',
            },
        )

        self.assertRedirects(supplier_response, reverse('dashboard:supplier_list'))
        self.assertRedirects(settings_response, reverse('dashboard:system_settings'))
        self.assertEqual(Supplier.objects.get().tax_id, '11222333000181')
        settings_record = SystemSettings.objects.get(pk=1)
        self.assertEqual(settings_record.company_name, 'Globo Vidraçaria e Construção')
        self.assertEqual(settings_record.financial_manager, 'Ana Financeiro')

    def test_managed_cash_transactions_must_be_changed_at_their_source(self):
        self.client.force_login(self.admin_user)
        self.client.post(
            reverse('dashboard:expense_create'),
            {
                'expense_date': '2026-08-10',
                'category': Expense.Category.WATER,
                'description': 'Conta de água',
                'amount': '100,00',
                'payment_method': CashTransaction.PaymentMethod.PIX,
                'supplier': '',
                'notes': '',
            },
        )
        expense = Expense.objects.get()

        edit_response = self.client.get(
            reverse('dashboard:cash_transaction_edit', args=[expense.cash_transaction_id])
        )
        delete_response = self.client.post(
            reverse('dashboard:cash_transaction_delete', args=[expense.cash_transaction_id])
        )

        self.assertRedirects(
            edit_response,
            reverse('dashboard:expense_edit', args=[expense.pk]),
        )
        self.assertRedirects(
            delete_response,
            f'{reverse("dashboard:cash_daily")}?date=2026-08-10',
        )
        self.assertTrue(Expense.objects.filter(pk=expense.pk).exists())
        self.assertTrue(CashTransaction.objects.filter(pk=expense.cash_transaction_id).exists())
