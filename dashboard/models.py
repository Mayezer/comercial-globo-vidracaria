from datetime import timedelta
from decimal import Decimal
from urllib.parse import quote

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

from accounts.models import Profile, normalize_text, only_digits, validate_cpf
from app.crypto import (
    EncryptedDecimalField,
    EncryptedEmailField,
    EncryptedTextField,
    blind_index,
)
from app.validators import validate_image_upload
from products.models import Product
from glazing_services.models import Service


class QuoteRequest(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pendente'
        COMPLETED = 'completed', 'Concluído'
        CANCELLED = 'cancelled', 'Cancelado'

    customer = models.ForeignKey(
        Profile,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='quote_requests',
        verbose_name='cliente',
    )
    products = models.ManyToManyField(Product, blank=True, related_name='quote_requests')
    services = models.ManyToManyField(Service, blank=True, related_name='quote_requests')
    details = EncryptedTextField('detalhes do pedido', blank=True, text_area=True)
    status = models.CharField(
        'status',
        max_length=12,
        choices=Status.choices,
        default=Status.PENDING,
    )
    requested_at = models.DateTimeField('solicitado em', auto_now_add=True, db_index=True)
    status_updated_at = models.DateTimeField('status atualizado em', null=True, blank=True)
    status_updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='last_updated_quotes',
        verbose_name='status atualizado por',
    )

    # Os dados essenciais ficam preservados mesmo se o cliente excluir a conta.
    customer_name = EncryptedTextField('nome do cliente', max_length=180)
    customer_account_type = models.CharField('tipo de pessoa', max_length=2)
    customer_document = EncryptedTextField('CPF ou CNPJ', max_length=14)
    customer_email = EncryptedEmailField('e-mail do cliente', max_length=254)
    customer_phone = EncryptedTextField('telefone do cliente', max_length=13, blank=True)
    customer_street = EncryptedTextField('rua', max_length=150)
    customer_neighborhood = EncryptedTextField('bairro', max_length=100)
    customer_house_number = EncryptedTextField('número', max_length=20)
    customer_reference_point = EncryptedTextField(
        'ponto de referência', max_length=180, blank=True
    )

    class Meta:
        ordering = ('-requested_at', '-id')
        verbose_name = 'solicitação de orçamento'
        verbose_name_plural = 'solicitações de orçamento'

    def __str__(self):
        return f'Orçamento #{self.pk} — {self.customer_name}'

    @classmethod
    def next_allowed_at_for(cls, customer):
        last_request = cls.objects.filter(customer=customer).order_by('-requested_at').first()
        if last_request is None:
            return None
        return last_request.requested_at + timedelta(hours=4)

    @classmethod
    def customer_can_request(cls, customer, now=None):
        next_allowed_at = cls.next_allowed_at_for(customer)
        return next_allowed_at is None or (now or timezone.now()) >= next_allowed_at

    def copy_customer_data(self, customer):
        self.customer = customer
        self.customer_name = customer.full_name or customer.corporate_name or customer.email
        self.customer_account_type = customer.account_type
        self.customer_document = customer.document
        self.customer_email = customer.email
        self.customer_phone = customer.phone
        self.customer_street = customer.street
        self.customer_neighborhood = customer.neighborhood
        self.customer_house_number = customer.house_number
        self.customer_reference_point = customer.reference_point

    @property
    def full_address(self):
        address = f'{self.customer_street}, nº {self.customer_house_number} — {self.customer_neighborhood}'
        if self.customer_reference_point:
            address += f' ({self.customer_reference_point})'
        return address

    @property
    def whatsapp_url(self):
        digits = ''.join(character for character in self.customer_phone if character.isdigit())
        if len(digits) in {10, 11}:
            digits = f'55{digits}'
        if len(digits) not in {12, 13}:
            return ''
        message = quote(
            f'Olá, {self.customer_name}! Recebemos sua solicitação de orçamento #{self.pk} '
            'na Globo Vidraçaria.'
        )
        return f'https://wa.me/{digits}?text={message}'

    @property
    def formatted_customer_document(self):
        if self.customer_account_type == Profile.AccountType.INDIVIDUAL and len(self.customer_document) == 11:
            return (
                f'{self.customer_document[:3]}.{self.customer_document[3:6]}.'
                f'{self.customer_document[6:9]}-{self.customer_document[9:]}'
            )
        if self.customer_account_type == Profile.AccountType.COMPANY and len(self.customer_document) == 14:
            return (
                f'{self.customer_document[:2]}.{self.customer_document[2:5]}.'
                f'{self.customer_document[5:8]}/{self.customer_document[8:12]}-'
                f'{self.customer_document[12:]}'
            )
        return self.customer_document

    @property
    def formatted_customer_phone(self):
        if len(self.customer_phone) == 11:
            return (
                f'({self.customer_phone[:2]}) {self.customer_phone[2:7]} - '
                f'{self.customer_phone[7:]}'
            )
        return self.customer_phone


class QuoteStatusHistory(models.Model):
    quote = models.ForeignKey(
        QuoteRequest,
        on_delete=models.CASCADE,
        related_name='status_history',
        verbose_name='orçamento',
    )
    status = models.CharField('status selecionado', max_length=12, choices=QuoteRequest.Status.choices)
    admin = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='quote_status_actions',
        verbose_name='administrador',
    )
    changed_at = models.DateTimeField('alterado em', auto_now_add=True)

    class Meta:
        ordering = ('-changed_at', '-id')
        verbose_name = 'histórico do orçamento'
        verbose_name_plural = 'históricos dos orçamentos'

    def __str__(self):
        return f'{self.quote} — {self.get_status_display()}'


class QuoteAdminNotification(models.Model):
    quote = models.ForeignKey(
        QuoteRequest,
        on_delete=models.CASCADE,
        related_name='admin_notifications',
    )
    admin = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='quote_notifications',
    )
    delivered_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=('quote', 'admin'),
                name='unique_quote_notification_per_admin',
            ),
        ]
        ordering = ('delivered_at',)


class CashTransaction(models.Model):
    class Kind(models.TextChoices):
        INCOME = 'income', 'Entrada'
        EXPENSE = 'expense', 'Saída'

    class PaymentMethod(models.TextChoices):
        CASH = 'cash', 'Dinheiro'
        PIX = 'pix', 'Pix'
        CREDIT_CARD = 'credit_card', 'Cartão de crédito'
        DEBIT_CARD = 'debit_card', 'Cartão de débito'

    transaction_date = models.DateField('data do lançamento', default=timezone.localdate, db_index=True)
    kind = models.CharField('tipo', max_length=7, choices=Kind.choices)
    description = EncryptedTextField('descrição', max_length=180)
    amount = EncryptedDecimalField(
        'valor',
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
    )
    payment_method = models.CharField(
        'forma de pagamento',
        max_length=12,
        choices=PaymentMethod.choices,
    )
    notes = EncryptedTextField('observações', blank=True, text_area=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='cash_transactions',
        verbose_name='cadastrado por',
    )
    created_at = models.DateTimeField('cadastrado em', auto_now_add=True)

    class Meta:
        ordering = ('-transaction_date', '-created_at', '-id')
        verbose_name = 'lançamento de caixa'
        verbose_name_plural = 'lançamentos de caixa'

    def __str__(self):
        return f'{self.get_kind_display()} — {self.description}'


class Employee(models.Model):
    photo = models.FileField(
        'foto',
        upload_to='employee_photos/',
        blank=True,
        validators=[validate_image_upload],
    )
    full_name = EncryptedTextField('nome completo', max_length=180)
    full_name_hash = models.CharField(
        max_length=64, blank=True, default='', db_index=True, editable=False
    )
    cpf = EncryptedTextField('CPF', max_length=11, validators=[validate_cpf])
    cpf_hash = models.CharField(max_length=64, unique=True, editable=False)
    monthly_salary = EncryptedDecimalField(
        'salário mensal',
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
    )
    created_at = models.DateTimeField('cadastrado em', auto_now_add=True)
    updated_at = models.DateTimeField('atualizado em', auto_now=True)

    class Meta:
        ordering = ('id',)
        verbose_name = 'funcionário'
        verbose_name_plural = 'funcionários'

    def clean(self):
        super().clean()
        self.cpf = only_digits(self.cpf)

    def save(self, *args, **kwargs):
        self.full_name = (self.full_name or '').strip()
        self.cpf = only_digits(self.cpf)
        self.full_name_hash = blind_index(normalize_text(self.full_name), 'employee.full_name')
        self.cpf_hash = blind_index(self.cpf, 'employee.cpf')
        update_fields = kwargs.get('update_fields')
        if update_fields:
            expanded = set(update_fields)
            if 'full_name' in expanded:
                expanded.add('full_name_hash')
            if 'cpf' in expanded:
                expanded.add('cpf_hash')
            kwargs['update_fields'] = tuple(expanded)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.full_name

    @property
    def formatted_cpf(self):
        if len(self.cpf) == 11:
            return f'{self.cpf[:3]}.{self.cpf[3:6]}.{self.cpf[6:9]}-{self.cpf[9:]}'
        return self.cpf

    @property
    def masked_cpf(self):
        return f'***.{self.cpf[3:6]}.{self.cpf[6:9]}-**' if len(self.cpf) == 11 else 'CPF protegido'


class Supplier(models.Model):
    name = EncryptedTextField('nome ou razão social', max_length=180)
    name_hash = models.CharField(max_length=64, blank=True, default='', db_index=True, editable=False)
    contact_name = EncryptedTextField('pessoa de contato', max_length=120, blank=True)
    contact_name_hash = models.CharField(
        max_length=64, blank=True, default='', db_index=True, editable=False
    )
    tax_id = EncryptedTextField('CPF ou CNPJ', max_length=14, blank=True)
    tax_id_hash = models.CharField(
        max_length=64, blank=True, default='', db_index=True, editable=False
    )
    phone = EncryptedTextField('telefone', max_length=13, blank=True)
    phone_hash = models.CharField(
        max_length=64, blank=True, default='', db_index=True, editable=False
    )
    email = EncryptedEmailField('e-mail', max_length=254, blank=True)
    email_hash = models.CharField(
        max_length=64, blank=True, default='', db_index=True, editable=False
    )
    address = EncryptedTextField('endereço', max_length=240, blank=True)
    notes = EncryptedTextField('observações', blank=True, text_area=True)
    is_active = models.BooleanField('fornecedor ativo', default=True)
    created_at = models.DateTimeField('cadastrado em', auto_now_add=True)
    updated_at = models.DateTimeField('atualizado em', auto_now=True)

    class Meta:
        ordering = ('id',)
        verbose_name = 'fornecedor'
        verbose_name_plural = 'fornecedores'

    def save(self, *args, **kwargs):
        self.name = (self.name or '').strip()
        self.contact_name = (self.contact_name or '').strip()
        self.tax_id = only_digits(self.tax_id)
        self.phone = only_digits(self.phone)
        self.email = (self.email or '').strip().lower()
        self.name_hash = blind_index(normalize_text(self.name), 'supplier.name')
        self.contact_name_hash = blind_index(
            normalize_text(self.contact_name), 'supplier.contact_name'
        )
        self.tax_id_hash = blind_index(self.tax_id, 'supplier.tax_id')
        self.phone_hash = blind_index(self.phone, 'supplier.phone')
        self.email_hash = blind_index(self.email, 'supplier.email')
        update_fields = kwargs.get('update_fields')
        if update_fields:
            related_hashes = {
                'name': 'name_hash',
                'contact_name': 'contact_name_hash',
                'tax_id': 'tax_id_hash',
                'phone': 'phone_hash',
                'email': 'email_hash',
            }
            expanded = set(update_fields)
            expanded.update(
                hash_field for source, hash_field in related_hashes.items() if source in expanded
            )
            kwargs['update_fields'] = tuple(expanded)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

    @property
    def formatted_tax_id(self):
        if len(self.tax_id) == 11:
            return f'{self.tax_id[:3]}.{self.tax_id[3:6]}.{self.tax_id[6:9]}-{self.tax_id[9:]}'
        if len(self.tax_id) == 14:
            return (
                f'{self.tax_id[:2]}.{self.tax_id[2:5]}.{self.tax_id[5:8]}/'
                f'{self.tax_id[8:12]}-{self.tax_id[12:]}'
            )
        return self.tax_id

    @property
    def masked_tax_id(self):
        if len(self.tax_id) == 11:
            return f'***.{self.tax_id[3:6]}.{self.tax_id[6:9]}-**'
        if len(self.tax_id) == 14:
            return f'**.{self.tax_id[2:5]}.{self.tax_id[5:8]}/****-**'
        return 'Documento protegido' if self.tax_id else ''


class Expense(models.Model):
    class Category(models.TextChoices):
        WATER = 'water', 'Água'
        ENERGY = 'energy', 'Energia'
        INTERNET = 'internet', 'Internet'
        LOSSES = 'losses', 'Perdas e avarias'
        TAXES = 'taxes', 'Impostos'
        LICENSES = 'licenses', 'Licenças'
        FREIGHT = 'freight', 'Fretes'
        INVENTORY = 'inventory', 'Produtos para estoque'
        MAINTENANCE = 'maintenance', 'Manutenção'
        RENT = 'rent', 'Aluguel'
        OTHER = 'other', 'Outros'

    expense_date = models.DateField('data do gasto', default=timezone.localdate, db_index=True)
    category = models.CharField('categoria', max_length=16, choices=Category.choices)
    description = models.CharField('descrição', max_length=180)
    amount = models.DecimalField(
        'valor',
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
    )
    payment_method = models.CharField(
        'forma de pagamento',
        max_length=12,
        choices=CashTransaction.PaymentMethod.choices,
    )
    supplier = models.ForeignKey(
        Supplier,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='expenses',
        verbose_name='fornecedor',
    )
    notes = models.TextField('observações', blank=True)
    cash_transaction = models.OneToOneField(
        CashTransaction,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='managed_expense',
        editable=False,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='managed_expenses',
        verbose_name='cadastrado por',
    )
    created_at = models.DateTimeField('cadastrado em', auto_now_add=True)
    updated_at = models.DateTimeField('atualizado em', auto_now=True)

    class Meta:
        ordering = ('-expense_date', '-created_at', '-id')
        verbose_name = 'gasto'
        verbose_name_plural = 'gastos'
        constraints = [
            models.CheckConstraint(
                condition=models.Q(amount__gt=0),
                name='expense_amount_greater_than_zero',
            ),
        ]

    def __str__(self):
        return f'{self.get_category_display()} — {self.description}'


class Payroll(models.Model):
    employee = models.ForeignKey(
        Employee,
        on_delete=models.PROTECT,
        related_name='payrolls',
        verbose_name='funcionário',
    )
    competence = models.DateField('competência', db_index=True)
    employee_name = EncryptedTextField('nome do funcionário', max_length=180, editable=False)
    employee_cpf = EncryptedTextField('CPF do funcionário', max_length=11, editable=False)
    employee_cpf_hash = models.CharField(
        max_length=64, blank=True, default='', db_index=True, editable=False
    )
    gross_salary = EncryptedDecimalField(
        'salário-base',
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
    )
    additions = EncryptedDecimalField(
        'acréscimos',
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
    )
    deductions = EncryptedDecimalField(
        'descontos',
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
    )
    payment_date = models.DateField('data do pagamento', default=timezone.localdate)
    payment_method = models.CharField(
        'forma de pagamento',
        max_length=12,
        choices=CashTransaction.PaymentMethod.choices,
        default=CashTransaction.PaymentMethod.PIX,
    )
    notes = EncryptedTextField('observações', blank=True, text_area=True)
    cash_transaction = models.OneToOneField(
        CashTransaction,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='payroll',
        editable=False,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='payrolls_created',
        verbose_name='cadastrado por',
    )
    created_at = models.DateTimeField('cadastrado em', auto_now_add=True)
    updated_at = models.DateTimeField('atualizado em', auto_now=True)

    class Meta:
        ordering = ('-competence', 'id')
        verbose_name = 'folha de pagamento'
        verbose_name_plural = 'folhas de pagamento'
        constraints = [
            models.UniqueConstraint(
                fields=('employee', 'competence'),
                name='unique_employee_payroll_per_competence',
            ),
        ]

    def save(self, *args, **kwargs):
        if self.competence:
            self.competence = self.competence.replace(day=1)
        if self.employee_id:
            self.employee_name = self.employee.full_name
            self.employee_cpf = self.employee.cpf
            self.employee_cpf_hash = blind_index(self.employee_cpf, 'payroll.employee_cpf')
            update_fields = kwargs.get('update_fields')
            if update_fields and ({'employee', 'employee_name', 'employee_cpf'} & set(update_fields)):
                kwargs['update_fields'] = tuple(
                    set(update_fields) | {'employee_name', 'employee_cpf', 'employee_cpf_hash'}
                )
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.employee_name} — {self.competence:%m/%Y}'

    @property
    def net_salary(self):
        return self.gross_salary + self.additions - self.deductions

    @property
    def formatted_employee_cpf(self):
        if len(self.employee_cpf) == 11:
            return (
                f'{self.employee_cpf[:3]}.{self.employee_cpf[3:6]}.'
                f'{self.employee_cpf[6:9]}-{self.employee_cpf[9:]}'
            )
        return self.employee_cpf


class SystemSettings(models.Model):
    company_name = models.CharField('nome da empresa', max_length=180, default='Globo Vidraçaria')
    tax_id = EncryptedTextField('CNPJ', max_length=14, blank=True)
    tax_id_hash = models.CharField(
        max_length=64, blank=True, default='', db_index=True, editable=False
    )
    phone = EncryptedTextField('telefone', max_length=13, blank=True)
    email = EncryptedEmailField('e-mail', max_length=254, blank=True)
    address = EncryptedTextField('endereço', max_length=240, blank=True)
    financial_manager = EncryptedTextField('responsável financeiro', max_length=180, blank=True)
    updated_at = models.DateTimeField('atualizado em', auto_now=True)

    class Meta:
        verbose_name = 'configuração do sistema'
        verbose_name_plural = 'configurações do sistema'

    def save(self, *args, **kwargs):
        self.pk = 1
        self.tax_id = only_digits(self.tax_id)
        self.phone = only_digits(self.phone)
        self.email = (self.email or '').strip().lower()
        self.tax_id_hash = blind_index(self.tax_id, 'system_settings.tax_id')
        update_fields = kwargs.get('update_fields')
        if update_fields and 'tax_id' in update_fields:
            kwargs['update_fields'] = tuple(set(update_fields) | {'tax_id_hash'})
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        instance, _ = cls.objects.get_or_create(pk=1)
        return instance

    def __str__(self):
        return self.company_name
