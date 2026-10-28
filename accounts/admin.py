from django.contrib import admin
from django.db.models import Q

from app.crypto import blind_index

from .models import Profile, normalize_text, only_digits


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('email', 'account_type', 'masked_document', 'full_name', 'email_verified_at')
    list_filter = ('account_type',)

    def get_search_results(self, request, queryset, search_term):
        queryset, use_distinct = super().get_search_results(request, queryset, search_term)
        if search_term:
            queryset = queryset.filter(
                Q(email_hash=blind_index(search_term.strip().lower(), 'profile.email'))
                | Q(document_hash=blind_index(only_digits(search_term), 'profile.document'))
                | Q(full_name_hash=blind_index(normalize_text(search_term), 'profile.full_name'))
                | Q(
                    corporate_name_hash=blind_index(
                        normalize_text(search_term), 'profile.corporate_name'
                    )
                )
            )
        return queryset, use_distinct
