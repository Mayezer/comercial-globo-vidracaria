from django.apps import AppConfig


class GlazingServicesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'glazing_services'
    # Mantém o rótulo interno e a tabela services_service para preservar os
    # dados e o histórico de migrações já existentes.
    label = 'services'
    verbose_name = 'glazing_services'
