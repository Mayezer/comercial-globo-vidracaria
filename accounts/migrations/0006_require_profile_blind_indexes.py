from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('accounts', '0005_encrypt_sensitive_data'),
    ]

    operations = [
        migrations.AlterField(
            model_name='profile',
            name='document_hash',
            field=models.CharField(editable=False, max_length=64, unique=True),
        ),
        migrations.AlterField(
            model_name='profile',
            name='email_hash',
            field=models.CharField(editable=False, max_length=64, unique=True),
        ),
    ]
