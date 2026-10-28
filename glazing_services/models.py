from django.db import models

from app.validators import validate_image_upload


class Service(models.Model):
    name = models.CharField('nome', max_length=160)
    service_type = models.CharField('tipo de serviço', max_length=120)
    description = models.TextField('descrição', blank=True)
    photo = models.FileField(
        'foto',
        upload_to='service_photos/',
        blank=True,
        validators=[validate_image_upload],
    )
    show_in_showcase = models.BooleanField(
        'exibir na vitrine do cliente',
        default=True,
        help_text='Desmarque para manter o serviço cadastrado sem exibi-lo aos clientes.',
    )

    class Meta:
        ordering = ('name', 'id')
        verbose_name = 'serviço'
        verbose_name_plural = 'serviços'

    def __str__(self):
        return self.name
