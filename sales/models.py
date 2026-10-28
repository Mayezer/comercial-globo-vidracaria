from decimal import Decimal, ROUND_HALF_UP

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

from accounts.models import Profile, normalize_text, only_digits, validate_cnpj, validate_cpf
from app.crypto import EncryptedEmailField, EncryptedTextField, blind_index
from calculator.models import Material
from dashboard.models import CashTransaction
from glazing_services.models import Service
from products.models import Product, ProductStockExit


MONEY_PLACES = Decimal('0.01')
AREA_PLACES = Decimal('0.000001')
ZERO_MONEY = Decimal('0.00')


def money(value):
    return Decimal(value or 0).quantize(MONEY_PLACES, rounding=ROUND_HALF_UP)


class Sale(models.Model):
    class Status(models.TextChoices):
        DRAFT = 'draft', 'Rascunho'
        COMPLETED = 'completed', 'Concluída'
        CANCELLED = 'cancelled', 'Cancelada'

    class CustomerType(models.TextChoices):
        REGISTERED = 'registered', 'Cliente cadastrado'
        WALK_IN_IDENTIFIED = 'walk_in_identified', 'Cliente Balcão identificado'
        WALK_IN_ANONYMOUS = 'walk_in_anonymous', 'Cliente Balcão não identificado'

    class PaymentStatus(models.TextChoices):
        PENDING = 'pending', 'Pendente'
        PAID = 'paid', 'Pago'
        REFUNDED = 'refunded', 'Estornado'

    status = models.CharField(
        'situação', max_length=12, choices=Status.choices, default=Status.DRAFT, db_index=True
    )
    employee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='responsible_sales',
        verbose_name='funcionário responsável',
    )
    customer_type = models.CharField(
        'tipo de cliente', max_length=20, choices=CustomerType.choices
    )
    customer = models.ForeignKey(
        Profile,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sales',
        verbose_name='cliente cadastrado',
    )
    customer_name = EncryptedTextField('nome congelado do cliente', max_length=180)
    customer_name_hash = models.CharField(
        max_length=64, blank=True, default='', db_index=True, editable=False
    )
    customer_document = EncryptedTextField('CPF/CNPJ congelado', max_length=14, blank=True)
    customer_document_hash = models.CharField(
        max_length=64, blank=True, default='', db_index=True, editable=False
    )
    customer_contact = EncryptedTextField('contato congelado', max_length=120, blank=True)
    customer_contact_hash = models.CharField(
        max_length=64, blank=True, default='', db_index=True, editable=False
    )
    customer_email = EncryptedEmailField('e-mail congelado', max_length=254, blank=True)
    customer_email_hash = models.CharField(
        max_length=64, blank=True, default='', db_index=True, editable=False
    )
    customer_address = EncryptedTextField('endereço congelado', max_length=500, blank=True)
    subtotal = models.DecimalField(
        'subtotal', max_digits=12, decimal_places=2, default=ZERO_MONEY,
        validators=[MinValueValidator(ZERO_MONEY)],
    )
    discount = models.DecimalField(
        'desconto da venda', max_digits=12, decimal_places=2, default=ZERO_MONEY,
        validators=[MinValueValidator(ZERO_MONEY)],
    )
    total = models.DecimalField(
        'total', max_digits=12, decimal_places=2, default=ZERO_MONEY,
        validators=[MinValueValidator(ZERO_MONEY)],
    )
    payment_method = models.CharField(
        'forma de pagamento', max_length=12, choices=CashTransaction.PaymentMethod.choices,
        blank=True,
    )
    payment_status = models.CharField(
        'situação do pagamento', max_length=10, choices=PaymentStatus.choices,
        default=PaymentStatus.PENDING,
    )
    amount_paid = models.DecimalField(
        'total pago', max_digits=12, decimal_places=2, default=ZERO_MONEY,
        validators=[MinValueValidator(ZERO_MONEY)],
    )
    notes = EncryptedTextField('observações', blank=True, text_area=True)
    cash_transaction = models.OneToOneField(
        CashTransaction,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='sale_payment',
        editable=False,
        verbose_name='lançamento de pagamento',
    )
    reversal_cash_transaction = models.OneToOneField(
        CashTransaction,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='sale_reversal',
        editable=False,
        verbose_name='lançamento de estorno',
    )
    created_at = models.DateTimeField('criada em', auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField('atualizada em', auto_now=True)
    completed_at = models.DateTimeField('concluída em', null=True, blank=True)
    cancelled_at = models.DateTimeField('cancelada em', null=True, blank=True)
    cancelled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='cancelled_sales',
        verbose_name='cancelada por',
    )
    cancellation_reason = EncryptedTextField(
        'motivo do cancelamento', blank=True, text_area=True
    )

    class Meta:
        ordering = ('-created_at', '-id')
        verbose_name = 'venda'
        verbose_name_plural = 'vendas'
        constraints = [
            models.CheckConstraint(condition=models.Q(subtotal__gte=0), name='sale_subtotal_nonnegative'),
            models.CheckConstraint(condition=models.Q(discount__gte=0), name='sale_discount_nonnegative'),
            models.CheckConstraint(condition=models.Q(total__gte=0), name='sale_total_nonnegative'),
            models.CheckConstraint(condition=models.Q(amount_paid__gte=0), name='sale_amount_paid_nonnegative'),
        ]

    def __str__(self):
        return f'{self.number} — {self.customer_name}'

    @property
    def number(self):
        return f'VEN-{self.pk:06d}' if self.pk else 'VEN-NOVA'

    @property
    def can_edit(self):
        return self.status == self.Status.DRAFT

    def copy_registered_customer(self):
        if not self.customer_id:
            return
        customer = self.customer
        self.customer_name = customer.full_name or customer.corporate_name or customer.email
        self.customer_document = customer.document
        self.customer_contact = customer.phone or customer.email
        self.customer_email = customer.email
        address_parts = [
            customer.street,
            f'nº {customer.house_number}' if customer.house_number else '',
            customer.neighborhood,
            customer.reference_point,
        ]
        self.customer_address = ', '.join(part for part in address_parts if part)

    def clean(self):
        super().clean()
        self.customer_document = only_digits(self.customer_document)
        if self.customer_type == self.CustomerType.REGISTERED:
            if not self.customer_id:
                raise ValidationError({'customer': 'Selecione um cliente cadastrado.'})
        elif self.customer_type == self.CustomerType.WALK_IN_IDENTIFIED:
            if not self.customer_name.strip():
                raise ValidationError({'customer_name': 'Informe o nome do cliente de balcão.'})
            if self.customer_document:
                if len(self.customer_document) == 11:
                    validate_cpf(self.customer_document)
                elif len(self.customer_document) == 14:
                    validate_cnpj(self.customer_document)
                else:
                    raise ValidationError({'customer_document': 'Informe um CPF ou CNPJ válido.'})
        elif self.customer_type == self.CustomerType.WALK_IN_ANONYMOUS:
            self.customer = None
            self.customer_name = 'Cliente Balcão'
            self.customer_document = ''
            self.customer_contact = ''
            self.customer_email = ''
            self.customer_address = ''
        self.discount = money(self.discount)
        self.amount_paid = money(self.amount_paid)

    def recalculate_totals(self, save=False):
        subtotal = sum((item.total for item in self.items.all()), ZERO_MONEY)
        self.subtotal = money(subtotal)
        self.discount = money(self.discount)
        if self.discount > self.subtotal:
            raise ValidationError({'discount': 'O desconto da venda não pode superar o subtotal.'})
        self.total = money(self.subtotal - self.discount)
        if save:
            self.save(update_fields=('subtotal', 'discount', 'total', 'updated_at'))
        return self.total

    def save(self, *args, **kwargs):
        self.customer_name = (self.customer_name or '').strip()
        self.customer_document = only_digits(self.customer_document)
        self.customer_contact = (self.customer_contact or '').strip()
        self.customer_email = (self.customer_email or '').strip().lower()
        self.customer_name_hash = blind_index(
            normalize_text(self.customer_name), 'sale.customer_name'
        )
        self.customer_document_hash = blind_index(
            self.customer_document, 'sale.customer_document'
        )
        self.customer_contact_hash = blind_index(
            normalize_text(self.customer_contact), 'sale.customer_contact'
        )
        self.customer_email_hash = blind_index(self.customer_email, 'sale.customer_email')
        update_fields = kwargs.get('update_fields')
        if update_fields and set(update_fields) & {
            'customer_name', 'customer_document', 'customer_contact', 'customer_email'
        }:
            kwargs['update_fields'] = tuple(
                set(update_fields)
                | {
                    'customer_name_hash',
                    'customer_document_hash',
                    'customer_contact_hash',
                    'customer_email_hash',
                }
            )
        super().save(*args, **kwargs)


class SaleItem(models.Model):
    class ItemType(models.TextChoices):
        PRODUCT = 'product', 'Produto'
        MATERIAL = 'material', 'Vidro/material por m²'
        SERVICE = 'service', 'Serviço'

    class Unit(models.TextChoices):
        UNIT = 'UN', 'unidade'
        SQUARE_METER = 'M2', 'm²'
        SERVICE = 'SV', 'serviço'

    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name='items', verbose_name='venda')
    item_type = models.CharField('tipo', max_length=10, choices=ItemType.choices)
    product = models.ForeignKey(
        Product, on_delete=models.PROTECT, null=True, blank=True,
        related_name='sale_items', verbose_name='produto',
    )
    material = models.ForeignKey(
        Material, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='sale_items', verbose_name='material',
    )
    service = models.ForeignKey(
        Service, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='sale_items', verbose_name='serviço',
    )
    description = models.CharField('descrição congelada', max_length=200)
    unit = models.CharField('unidade congelada', max_length=2, choices=Unit.choices)
    quantity = models.DecimalField(
        'quantidade congelada', max_digits=14, decimal_places=6,
        validators=[MinValueValidator(Decimal('0.000001'))],
    )
    unit_price = models.DecimalField(
        'preço unitário congelado', max_digits=12, decimal_places=2,
        validators=[MinValueValidator(ZERO_MONEY)],
    )
    discount = models.DecimalField(
        'desconto do item', max_digits=12, decimal_places=2, default=ZERO_MONEY,
        validators=[MinValueValidator(ZERO_MONEY)],
    )
    total = models.DecimalField(
        'total congelado', max_digits=12, decimal_places=2, default=ZERO_MONEY,
        validators=[MinValueValidator(ZERO_MONEY)],
    )
    width_mm = models.DecimalField(
        'largura (mm)', max_digits=10, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(Decimal('0.01'))],
    )
    height_mm = models.DecimalField(
        'altura (mm)', max_digits=10, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(Decimal('0.01'))],
    )
    piece_count = models.PositiveIntegerField('quantidade de peças', null=True, blank=True)
    area_sqm = models.DecimalField(
        'área calculada (m²)', max_digits=14, decimal_places=6, null=True, blank=True,
        validators=[MinValueValidator(Decimal('0.000001'))],
    )
    created_at = models.DateTimeField('incluído em', auto_now_add=True)

    class Meta:
        ordering = ('id',)
        verbose_name = 'item da venda'
        verbose_name_plural = 'itens da venda'
        constraints = [
            models.CheckConstraint(condition=models.Q(quantity__gt=0), name='sale_item_quantity_positive'),
            models.CheckConstraint(condition=models.Q(unit_price__gte=0), name='sale_item_unit_price_nonnegative'),
            models.CheckConstraint(condition=models.Q(discount__gte=0), name='sale_item_discount_nonnegative'),
            models.CheckConstraint(condition=models.Q(total__gte=0), name='sale_item_total_nonnegative'),
        ]

    def __str__(self):
        return f'{self.description} — {self.quantity} {self.unit}'

    def clean(self):
        super().clean()
        current_sale_status = (
            Sale.objects.only('status').get(pk=self.sale_id).status if self.sale_id else None
        )
        if current_sale_status and current_sale_status != Sale.Status.DRAFT:
            original = SaleItem.objects.filter(pk=self.pk).first() if self.pk else None
            if original is None or any(
                getattr(original, field) != getattr(self, field)
                for field in ('description', 'quantity', 'unit_price', 'discount', 'total')
            ):
                raise ValidationError('Itens de uma venda concluída ou cancelada não podem ser alterados.')
        if self.item_type == self.ItemType.PRODUCT:
            if not self.product_id:
                raise ValidationError({'product': 'Selecione um produto.'})
            if self.quantity != self.quantity.to_integral_value():
                raise ValidationError({'quantity': 'Produtos devem ser vendidos em quantidades inteiras.'})
            self.unit = self.Unit.UNIT
            self.description = self.description or self.product.name
            gross = self.quantity * self.unit_price
            self.width_mm = self.height_mm = self.area_sqm = None
            self.piece_count = None
        elif self.item_type == self.ItemType.MATERIAL:
            if not self.material_id:
                raise ValidationError({'material': 'Selecione um vidro ou material.'})
            if self.material.unit_type != Material.UnitType.SQUARE_METER:
                raise ValidationError({'material': 'Selecione um material cadastrado por metro quadrado.'})
            if not self.width_mm or not self.height_mm or not self.piece_count:
                raise ValidationError('Informe largura, altura e quantidade de peças.')
            area = (
                Decimal(self.width_mm) * Decimal(self.height_mm) * Decimal(self.piece_count)
                / Decimal('1000000')
            ).quantize(AREA_PLACES)
            self.area_sqm = area
            self.quantity = area
            self.unit = self.Unit.SQUARE_METER
            self.description = self.description or self.material.name
            gross = area * self.unit_price
            self.product = None
            self.service = None
        elif self.item_type == self.ItemType.SERVICE:
            if not self.service_id:
                raise ValidationError({'service': 'Selecione um serviço.'})
            self.unit = self.Unit.SERVICE
            self.description = self.description or self.service.name
            gross = self.quantity * self.unit_price
            self.product = None
            self.material = None
            self.width_mm = self.height_mm = self.area_sqm = None
            self.piece_count = None
        else:
            raise ValidationError({'item_type': 'Tipo de item inválido.'})

        self.unit_price = money(self.unit_price)
        self.discount = money(self.discount)
        gross = money(gross)
        if self.discount > gross:
            raise ValidationError({'discount': 'O desconto do item não pode superar seu valor bruto.'})
        self.total = money(gross - self.discount)

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class SaleStockMovement(models.Model):
    class Kind(models.TextChoices):
        EXIT = 'exit', 'Baixa da venda'
        RETURN = 'return', 'Devolução por cancelamento'

    sale = models.ForeignKey(Sale, on_delete=models.PROTECT, related_name='stock_movements')
    sale_item = models.ForeignKey(SaleItem, on_delete=models.PROTECT, related_name='stock_movements')
    product = models.ForeignKey(
        Product, on_delete=models.PROTECT, related_name='sale_stock_movements'
    )
    kind = models.CharField('tipo', max_length=6, choices=Kind.choices)
    quantity = models.PositiveIntegerField('quantidade')
    stock_before = models.PositiveIntegerField('estoque anterior')
    stock_after = models.PositiveIntegerField('estoque posterior')
    product_stock_exit = models.OneToOneField(
        ProductStockExit,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='sale_movement',
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
        related_name='sale_stock_movements',
    )
    created_at = models.DateTimeField('registrada em', auto_now_add=True)

    class Meta:
        ordering = ('created_at', 'id')
        verbose_name = 'movimentação de estoque da venda'
        verbose_name_plural = 'movimentações de estoque das vendas'
        constraints = [
            models.UniqueConstraint(
                fields=('sale_item', 'kind'), name='unique_sale_item_stock_movement_kind'
            ),
            models.CheckConstraint(condition=models.Q(quantity__gt=0), name='sale_stock_quantity_positive'),
            models.CheckConstraint(
                condition=(
                    models.Q(
                        kind='exit',
                        stock_before=models.F('stock_after') + models.F('quantity'),
                    )
                    | models.Q(
                        kind='return',
                        stock_after=models.F('stock_before') + models.F('quantity'),
                    )
                ),
                name='sale_stock_balance_matches_kind',
            ),
        ]

    def __str__(self):
        return f'{self.sale.number} — {self.get_kind_display()} — {self.product}'
