import app.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0002_profile_email_verified_at'),
    ]

    operations = [
        migrations.AlterField(
            model_name='profile',
            name='profile_photo',
            field=models.FileField(
                blank=True,
                upload_to='profile_photos/',
                validators=[app.validators.validate_image_upload],
                verbose_name='foto de perfil',
            ),
        ),
    ]
