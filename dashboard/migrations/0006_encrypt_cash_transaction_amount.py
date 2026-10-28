from decimal import Decimal

import django.core.validators
from django.db import migrations

import app.crypto


def protect_amounts(apps, schema_editor):
    from app.crypto import active_encryption_key

    active_encryption_key()
    CashTransaction = apps.get_model('dashboard', 'CashTransaction')
    for transaction in CashTransaction.objects.all().iterator(chunk_size=500):
        transaction.save(update_fields=('amount',))


def restore_amounts(apps, schema_editor):
    from app.crypto import decrypt_value

    quote_name = schema_editor.connection.ops.quote_name
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            f'SELECT {quote_name("id")}, {quote_name("amount")} '
            f'FROM {quote_name("dashboard_cashtransaction")}'
        )
        for pk, value in cursor.fetchall():
            cursor.execute(
                f'UPDATE {quote_name("dashboard_cashtransaction")} '
                f'SET {quote_name("amount")} = %s WHERE {quote_name("id")} = %s',
                [decrypt_value(value, 'dashboard.cashtransaction.amount'), pk],
            )


class Migration(migrations.Migration):
    dependencies = [
        ('dashboard', '0005_require_employee_cpf_blind_index'),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name='cashtransaction',
            name='cash_transaction_amount_greater_than_zero',
        ),
        migrations.AlterField(
            model_name='cashtransaction',
            name='amount',
            field=app.crypto.EncryptedDecimalField(
                decimal_places=2,
                max_digits=12,
                validators=[django.core.validators.MinValueValidator(Decimal('0.01'))],
                verbose_name='valor',
            ),
        ),
        migrations.RunPython(protect_amounts, restore_amounts),
    ]
