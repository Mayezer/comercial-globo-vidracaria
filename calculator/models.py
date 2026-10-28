from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models


class Material(models.Model):
    class UnitType(models.TextChoices):
        SQUARE_METER = 'M2', 'Metro quadrado (m²)'
        LINEAR_METER = 'ML', 'Metro linear (metro reto)'

    name = models.CharField('nome', max_length=160, unique=True)
    unit_type = models.CharField(
        'tipo de medida',
        max_length=2,
        choices=UnitType.choices,
    )
    unit_price = models.DecimalField(
        'valor por unidade',
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
    )

    class Meta:
        ordering = ('name', 'id')
        verbose_name = 'material'
        verbose_name_plural = 'materiais'

    def __str__(self):
        return self.name
