import json

from django.conf import settings


COMPANY_NAME = 'Globo Vidraçaria e Materiais para Construção'
COMPANY_DESCRIPTION = (
    'Vidraçaria com produtos em vidro, alumínio e acrílico, materiais para construção '
    'e serviços de instalação e manutenção de vidros.'
)
PUBLIC_PHONE_NUMBERS = ('+55 93 99108-4346', '+55 93 99106-3146', '+55 93 3515-4346')
PUBLIC_STREET_ADDRESS = 'Rodovia Ernesto Acioly, nº 2505 — Bairro Aparecida'


def public_site(request):
    canonical_url = f'{settings.PUBLIC_SITE_URL}{request.path}'
    local_business = {
        '@context': 'https://schema.org',
        '@type': 'LocalBusiness',
        'name': COMPANY_NAME,
        'description': COMPANY_DESCRIPTION,
        'url': settings.PUBLIC_SITE_URL,
        'telephone': list(PUBLIC_PHONE_NUMBERS),
        'address': {
            '@type': 'PostalAddress',
            'streetAddress': PUBLIC_STREET_ADDRESS,
        },
        'sameAs': [
            'https://www.instagram.com/globovidracaria',
            'https://www.facebook.com/share/18bVcEA4Lu/',
        ],
    }
    return {
        'public_site_url': settings.PUBLIC_SITE_URL,
        'canonical_url': canonical_url,
        'google_site_verification': settings.GOOGLE_SITE_VERIFICATION,
        'local_business_json_ld': json.dumps(
            local_business,
            ensure_ascii=False,
            separators=(',', ':'),
        ),
    }
