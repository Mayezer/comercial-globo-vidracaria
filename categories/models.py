from django.db import models


class Category(models.Model):
    name = models.CharField('nome', max_length=100, unique=True)

    class Meta:
        ordering = ('name',)
        verbose_name = 'categoria'
        verbose_name_plural = 'categorias'

    def __str__(self):
        return self.name
