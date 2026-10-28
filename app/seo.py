from urllib.parse import urljoin

from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.http import require_GET

from glazing_services.models import Service
from products.models import Product

from .context_processors import COMPANY_DESCRIPTION, COMPANY_NAME, PUBLIC_PHONE_NUMBERS


def absolute_url(path):
    return urljoin(f'{settings.PUBLIC_SITE_URL}/', path.lstrip('/'))


def single_line(value):
    return ' '.join((value or '').split())


@require_GET
def sitemap_xml(request):
    urls = [
        absolute_url(reverse('home')),
        absolute_url(reverse('products:list')),
        absolute_url(reverse('glazing_services:list')),
    ]
    urls.extend(
        absolute_url(reverse('products:detail', kwargs={'pk': pk}))
        for pk in Product.objects.filter(show_in_showcase=True).values_list('pk', flat=True)
    )
    urls.extend(
        absolute_url(reverse('glazing_services:detail', kwargs={'pk': pk}))
        for pk in Service.objects.filter(show_in_showcase=True).values_list('pk', flat=True)
    )
    response = render(request, 'seo/sitemap.xml', {'urls': urls}, content_type='application/xml')
    response.headers['Cache-Control'] = 'public, max-age=900'
    return response


@require_GET
def robots_txt(request):
    lines = [
        'User-agent: *',
        'Allow: /',
        'Disallow: /admin/',
        'Disallow: /painel/',
        'Disallow: /perfil/',
        'Disallow: /entrar/',
        'Disallow: /criar-conta/',
        'Disallow: /sair/',
        'Disallow: /excluir-conta/',
        'Disallow: /orcamento/',
        f'Sitemap: {absolute_url(reverse("sitemap"))}',
    ]
    return HttpResponse('\n'.join(lines) + '\n', content_type='text/plain; charset=utf-8')


@require_GET
def llms_txt(request):
    product_names = list(
        Product.objects.filter(show_in_showcase=True).values_list('name', flat=True)[:20]
    )
    service_names = list(
        Service.objects.filter(show_in_showcase=True).values_list('name', flat=True)[:20]
    )
    lines = [
        f'# {COMPANY_NAME}',
        '',
        COMPANY_DESCRIPTION,
        '',
        '## Páginas públicas',
        f'- Início: {absolute_url(reverse("home"))}',
        f'- Produtos: {absolute_url(reverse("products:list"))}',
        f'- Serviços: {absolute_url(reverse("glazing_services:list"))}',
    ]
    if product_names:
        lines.extend(
            ('', '## Produtos publicados', f'- {"; ".join(map(single_line, product_names))}')
        )
    if service_names:
        lines.extend(
            ('', '## Serviços publicados', f'- {"; ".join(map(single_line, service_names))}')
        )
    lines.extend(
        (
            '',
            '## Contato público',
            f'- Telefones: {" / ".join(PUBLIC_PHONE_NUMBERS)}',
            f'- WhatsApp: https://wa.me/5593991063146',
        )
    )
    return HttpResponse('\n'.join(lines) + '\n', content_type='text/plain; charset=utf-8')
