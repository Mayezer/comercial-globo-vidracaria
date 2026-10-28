import app.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='product',
            name='photo',
            field=models.FileField(
                blank=True,
                upload_to='product_photos/',
                validators=[app.validators.validate_image_upload],
                verbose_name='foto',
            ),
        ),
    ]
