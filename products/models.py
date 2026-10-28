from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models

from app.validators import validate_image_upload
from categories.models import Category


class Product(models.Model):
    name = models.CharField('nome', max_length=160)
    photo = models.FileField(
        'foto',
        upload_to='product_photos/',
        blank=True,
        validators=[validate_image_upload],
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name='products',
        verbose_name='categoria',
    )
    price = models.DecimalField(
        'preço',
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
    )
    stock_quantity = models.PositiveIntegerField(
        'quantidade em estoque',
        default=0,
        validators=[MinValueValidator(0)],
        help_text='Informe quantas unidades deste produto estão disponíveis.',
    )
    description = models.TextField('descrição', blank=True)
    show_in_showcase = models.BooleanField(
        'exibir na vitrine do cliente',
        default=True,
        help_text='Desmarque para manter o produto cadastrado sem exibi-lo aos clientes.',
    )

    class Meta:
        ordering = ('name', 'id')
        verbose_name = 'produto'
        verbose_name_plural = 'produtos'

    def __str__(self):
        return self.name


class ProductStockExit(models.Model):
    product = models.ForeignKey(
        Product,
        on_delete=models.SET_NULL,
        null=True,
        related_name='stock_exits',
        verbose_name='produto',
    )
    product_name = models.CharField('nome do produto', max_length=160)
    quantity = models.PositiveIntegerField(
        'quantidade retirada',
        validators=[MinValueValidator(1)],
    )
    stock_before = models.PositiveIntegerField('estoque anterior')
    stock_after = models.PositiveIntegerField('estoque após a saída')
    notes = models.CharField('observação', max_length=240, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='product_stock_exits',
        verbose_name='registrado por',
    )
    created_at = models.DateTimeField('registrado em', auto_now_add=True, db_index=True)

    class Meta:
        ordering = ('-created_at', '-id')
        verbose_name = 'saída de produto'
        verbose_name_plural = 'saídas de produtos'
        constraints = [
            models.CheckConstraint(
                condition=models.Q(quantity__gt=0),
                name='product_stock_exit_quantity_greater_than_zero',
            ),
            models.CheckConstraint(
                condition=models.Q(
                    stock_before=models.F('stock_after') + models.F('quantity')
                ),
                name='product_stock_exit_balance_matches_quantity',
            ),
        ]

    def __str__(self):
        return f'{self.product_name} — {self.quantity} unidade(s)'
