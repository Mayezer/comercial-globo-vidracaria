import app.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('services', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='service',
            name='photo',
            field=models.FileField(
                blank=True,
                upload_to='service_photos/',
                validators=[app.validators.validate_image_upload],
                verbose_name='foto',
            ),
        ),
    ]
