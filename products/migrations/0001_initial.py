import decimal

import django.core.validators
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ('categories', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Product',
            fields=[
                (
                    'id',
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name='ID',
                    ),
                ),
                ('name', models.CharField(max_length=160, verbose_name='nome')),
                (
                    'photo',
                    models.FileField(
                        blank=True,
                        upload_to='product_photos/',
                        validators=[
                            django.core.validators.FileExtensionValidator(
                                ['jpg', 'jpeg', 'png', 'webp'],
                            ),
                        ],
                        verbose_name='foto',
                    ),
                ),
                (
                    'price',
                    models.DecimalField(
                        decimal_places=2,
                        max_digits=10,
                        validators=[django.core.validators.MinValueValidator(decimal.Decimal('0.00'))],
                        verbose_name='preço',
                    ),
                ),
                ('description', models.TextField(blank=True, verbose_name='descrição')),
                (
                    'category',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name='products',
                        to='categories.category',
                        verbose_name='categoria',
                    ),
                ),
            ],
            options={
                'verbose_name': 'produto',
                'verbose_name_plural': 'produtos',
                'ordering': ('name', 'id'),
            },
        ),
    ]
