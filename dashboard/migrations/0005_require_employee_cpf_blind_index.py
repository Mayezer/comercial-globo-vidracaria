from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('accounts', '0005_encrypt_sensitive_data'),
        ('dashboard', '0004_alter_employee_options_alter_payroll_options_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='employee',
            name='cpf_hash',
            field=models.CharField(editable=False, max_length=64, unique=True),
        ),
    ]
