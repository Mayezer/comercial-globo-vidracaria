from django.contrib import admin

from .models import Service


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'service_type', 'show_in_showcase')
    list_filter = ('show_in_showcase', 'service_type')
    ordering = ('name',)
    readonly_fields = ('id',)
    search_fields = ('name', 'service_type', 'description')
    fieldsets = (
        ('Identificação', {'fields': ('id', 'name', 'service_type')}),
        ('Apresentação', {'fields': ('show_in_showcase', 'photo', 'description')}),
    )
