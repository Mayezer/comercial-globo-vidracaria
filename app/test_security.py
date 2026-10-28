from decimal import Decimal
from datetime import date
from io import StringIO
import base64
import logging

from django.contrib.auth import get_user_model
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.core.management import call_command
from django.db import connection
from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.models import Profile
from categories.models import Category
from dashboard.models import (
    CashTransaction,
    Employee,
    Payroll,
    QuoteRequest,
    Supplier,
    SystemSettings,
)
from glazing_services.models import Service
from products.models import Product
from sales.models import Sale

from .crypto import (
    SensitiveDataError,
    blind_index,
    decrypt_value,
    encrypt_value,
    matches_blind_index,
)
from .logging import RedactingFormatter


KEY_V1 = 'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA='
KEY_V2 = 'AgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgI='
HASH_KEY = 'AQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQE='

User = get_user_model()


@override_settings(
    FIELD_ENCRYPTION_KEYS=f'v1:{KEY_V1}',
    FIELD_ENCRYPTION_ACTIVE_KEY='v1',
    FIELD_HASH_KEY=HASH_KEY,
)
class CryptographyTests(TestCase):
    def test_authenticated_encryption_round_trip_and_random_nonce(self):
        first = encrypt_value('dado pessoal', 'test.field')
        second = encrypt_value('dado pessoal', 'test.field')

        self.assertNotEqual(first, second)
        self.assertTrue(first.startswith('enc$v1$'))
        self.assertEqual(decrypt_value(first, 'test.field'), 'dado pessoal')

    def test_invalid_ciphertext_and_wrong_context_are_rejected(self):
        encrypted = encrypt_value('dado pessoal', 'test.field')
        prefix, version, nonce, encoded_ciphertext = encrypted.split('$', 3)
        ciphertext = bytearray(base64.urlsafe_b64decode(
            encoded_ciphertext + ('=' * (-len(encoded_ciphertext) % 4))
        ))
        # Altera um byte real; mudar apenas os bits de padding do Base64 pode
        # representar o mesmo ciphertext e tornar o teste instável.
        ciphertext[0] ^= 1
        tampered = base64.urlsafe_b64encode(ciphertext).decode('ascii').rstrip('=')

        with self.assertRaises(SensitiveDataError):
            decrypt_value(f'{prefix}${version}${nonce}${tampered}', 'test.field')
        with self.assertRaises(SensitiveDataError):
            decrypt_value(encrypted, 'other.field')

    def test_missing_key_fails_closed(self):
        with override_settings(FIELD_ENCRYPTION_KEYS=''):
            with self.assertRaises(ImproperlyConfigured):
                encrypt_value('segredo', 'test.field')

    def test_key_rotation_reads_old_ciphertext_and_writes_active_version(self):
        old_ciphertext = encrypt_value('valor rotacionável', 'test.field')
        with override_settings(
            FIELD_ENCRYPTION_KEYS=f'v1:{KEY_V1},v2:{KEY_V2}',
            FIELD_ENCRYPTION_ACTIVE_KEY='v2',
        ):
            self.assertEqual(
                decrypt_value(old_ciphertext, 'test.field'),
                'valor rotacionável',
            )
            self.assertTrue(encrypt_value('novo valor', 'test.field').startswith('enc$v2$'))

    def test_blind_index_is_stable_and_constant_time_helper_matches(self):
        digest = blind_index('52998224725', 'profile.document')

        self.assertEqual(digest, blind_index('52998224725', 'profile.document'))
        self.assertNotEqual(digest, blind_index('52998224725', 'employee.cpf'))
        self.assertTrue(matches_blind_index('52998224725', digest, 'profile.document'))
        self.assertFalse(matches_blind_index('11222333000181', digest, 'profile.document'))

    def raw_value(self, table, column, pk):
        quote = connection.ops.quote_name
        with connection.cursor() as cursor:
            cursor.execute(
                f'SELECT {quote(column)} FROM {quote(table)} WHERE {quote("id")} = %s',
                [pk],
            )
            return cursor.fetchone()[0]

    def test_sensitive_model_fields_are_ciphertext_at_rest_and_searchable_by_hmac(self):
        user = User.objects.create_user(username='opaque-account', password='Senha-Forte-2026')
        profile = Profile.objects.create(
            user=user,
            account_type=Profile.AccountType.INDIVIDUAL,
            document='52998224725',
            email='cliente@example.com',
            full_name='Maria Cliente',
            street='Rua das Flores',
            neighborhood='Centro',
            house_number='25',
            phone='93999999999',
        )
        employee = Employee.objects.create(
            full_name='João Funcionário',
            cpf='11144477735',
            monthly_salary=Decimal('2500.00'),
        )
        cash_transaction = CashTransaction.objects.create(
            transaction_date=date(2026, 8, 31),
            kind=CashTransaction.Kind.EXPENSE,
            description='Folha de pagamento',
            amount=Decimal('2550.00'),
            payment_method=CashTransaction.PaymentMethod.PIX,
        )
        payroll = Payroll.objects.create(
            employee=employee,
            competence=date(2026, 8, 1),
            gross_salary=Decimal('2500.00'),
            additions=Decimal('100.00'),
            deductions=Decimal('50.00'),
            cash_transaction=cash_transaction,
        )
        supplier = Supplier.objects.create(
            name='Fornecedor Teste',
            tax_id='11222333000181',
            email='fornecedor@example.com',
            phone='93988887777',
            address='Endereço reservado',
        )
        quote = QuoteRequest(details='Box para banheiro')
        quote.copy_customer_data(profile)
        quote.save()
        system_settings = SystemSettings.objects.create(
            tax_id='11222333000181',
            phone='93991063146',
            email='publico@example.com',
            address='Endereço da empresa',
            financial_manager='Responsável Financeiro',
        )
        sale = Sale.objects.create(
            employee=user,
            customer_type=Sale.CustomerType.REGISTERED,
            customer=profile,
            customer_name=profile.full_name,
            customer_document=profile.document,
            customer_contact=profile.phone,
            customer_email=profile.email,
            customer_address='Rua das Flores, 25',
        )

        checks = (
            ('accounts_profile', 'document', profile.pk, profile.document),
            ('accounts_profile', 'email', profile.pk, profile.email),
            ('dashboard_employee', 'cpf', employee.pk, employee.cpf),
            ('dashboard_employee', 'monthly_salary', employee.pk, '2500.00'),
            ('dashboard_cashtransaction', 'amount', cash_transaction.pk, '2550.00'),
            ('dashboard_payroll', 'gross_salary', payroll.pk, '2500.00'),
            ('dashboard_supplier', 'email', supplier.pk, supplier.email),
            ('dashboard_quoterequest', 'customer_document', quote.pk, profile.document),
            ('dashboard_systemsettings', 'financial_manager', system_settings.pk, 'Responsável Financeiro'),
            ('sales_sale', 'customer_document', sale.pk, profile.document),
        )
        for table, column, pk, plaintext in checks:
            with self.subTest(table=table, column=column):
                stored = self.raw_value(table, column, pk)
                self.assertTrue(stored.startswith('enc$v1$'))
                self.assertNotIn(str(plaintext), stored)

        self.assertEqual(
            Profile.objects.get(document_hash=profile.document_hash),
            profile,
        )
        employee.refresh_from_db()
        self.assertEqual(employee.monthly_salary, Decimal('2500.00'))
        payroll.refresh_from_db()
        self.assertEqual(payroll.net_salary, Decimal('2550.00'))

    def test_rotation_command_is_preview_only_until_explicitly_applied(self):
        user = User.objects.create_user(username='rotation-account', password='Senha-Forte-2026')
        profile = Profile.objects.create(
            user=user,
            account_type=Profile.AccountType.INDIVIDUAL,
            document='52998224725',
            email='rotation@example.com',
        )
        original = self.raw_value('accounts_profile', 'document', profile.pk)
        preview = StringIO()
        call_command('rotate_sensitive_data', stdout=preview)
        self.assertIn('seriam recriptografados', preview.getvalue())
        self.assertEqual(self.raw_value('accounts_profile', 'document', profile.pk), original)

        with override_settings(
            FIELD_ENCRYPTION_KEYS=f'v1:{KEY_V1},v2:{KEY_V2}',
            FIELD_ENCRYPTION_ACTIVE_KEY='v2',
        ):
            call_command('rotate_sensitive_data', apply=True, stdout=StringIO())
            rotated = self.raw_value('accounts_profile', 'document', profile.pk)
            self.assertTrue(rotated.startswith('enc$v2$'))
            self.assertEqual(
                decrypt_value(rotated, 'accounts.profile.document'),
                '52998224725',
            )


@override_settings(CORS_ALLOWED_ORIGINS=['https://catalogo-parceiro.example'])
class RestrictedCORSTests(TestCase):
    def test_allowed_origin_receives_cors_only_on_public_read_only_pages(self):
        response = self.client.get(
            reverse('products:list'),
            HTTP_ORIGIN='https://catalogo-parceiro.example',
        )
        private = self.client.get(
            reverse('accounts:profile'),
            HTTP_ORIGIN='https://catalogo-parceiro.example',
        )

        self.assertEqual(
            response.headers['Access-Control-Allow-Origin'],
            'https://catalogo-parceiro.example',
        )
        self.assertNotIn('Access-Control-Allow-Credentials', response.headers)
        self.assertNotIn('Access-Control-Allow-Origin', private.headers)

    def test_disallowed_and_absent_origins_receive_no_cors_headers(self):
        disallowed = self.client.get(
            reverse('products:list'),
            HTTP_ORIGIN='https://evil.example',
        )
        absent = self.client.get(reverse('products:list'))

        self.assertNotIn('Access-Control-Allow-Origin', disallowed.headers)
        self.assertNotIn('Access-Control-Allow-Origin', absent.headers)

    def test_preflight_allows_get_but_rejects_post(self):
        allowed = self.client.options(
            reverse('products:list'),
            HTTP_ORIGIN='https://catalogo-parceiro.example',
            HTTP_ACCESS_CONTROL_REQUEST_METHOD='GET',
        )
        denied = self.client.options(
            reverse('products:list'),
            HTTP_ORIGIN='https://catalogo-parceiro.example',
            HTTP_ACCESS_CONTROL_REQUEST_METHOD='POST',
        )

        self.assertEqual(allowed.status_code, 204)
        self.assertEqual(denied.status_code, 405)
        self.assertNotIn('Access-Control-Allow-Credentials', allowed.headers)


class InjectionInputTests(TestCase):
    def test_typical_sql_injection_strings_do_not_change_public_queries(self):
        category = Category.objects.create(name='Vidros')
        Product.objects.create(name='Produto público', category=category, price=Decimal('10.00'))
        Service.objects.create(name='Serviço público', service_type='Instalação')

        products = self.client.get(reverse('products:list'), {'page': "1' OR '1'='1"})
        login = self.client.post(
            reverse('accounts:login'),
            {'identifier': "' OR 1=1 --", 'password': 'qualquer'},
        )

        self.assertEqual(products.status_code, 200)
        self.assertEqual(len(products.context['products']), 1)
        self.assertEqual(login.status_code, 200)
        self.assertNotIn('_auth_user_id', self.client.session)
        self.assertNotContains(login, 'OperationalError')


class LoggingRedactionTests(TestCase):
    def test_formatter_removes_tokens_documents_emails_and_bearer_credentials(self):
        record = logging.LogRecord(
            name='django.request',
            level=logging.ERROR,
            pathname=__file__,
            lineno=1,
            msg=(
                'Falha em /confirmar-email/token-assinado-secreto/?token=outro-segredo '
                'para 529.982.247-25 e cliente@example.com; Authorization: Bearer abc.def.ghi'
            ),
            args=(),
            exc_info=None,
        )

        output = RedactingFormatter('%(message)s').format(record)

        for sensitive in (
            'token-assinado-secreto',
            'outro-segredo',
            '529.982.247-25',
            'cliente@example.com',
            'abc.def.ghi',
        ):
            self.assertNotIn(sensitive, output)
        self.assertIn('[redacted]', output)
