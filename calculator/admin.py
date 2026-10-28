from django.contrib import admin

from .models import Material


@admin.register(Material)
class MaterialAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'unit_type', 'unit_price')
    list_filter = ('unit_type',)
    ordering = ('name',)
    readonly_fields = ('id',)
    search_fields = ('name',)
