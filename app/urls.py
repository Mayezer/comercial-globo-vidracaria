"""
URL configuration for app project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.contrib.auth.views import LogoutView
from django.conf import settings
from django.conf.urls.static import static
from django.urls import include, path
from django.views.generic import RedirectView

from accounts import views as accounts_views
from showcase import views as showcase_views
from app import seo


accounts_patterns = (
    [
        path('criar-conta/', accounts_views.register, name='register'),
        path('entrar/', accounts_views.login, name='login'),
        path('perfil/', accounts_views.profile, name='profile'),
        path('perfil/editar/', accounts_views.edit_profile, name='edit_profile'),
        path(
            'perfil/reenviar-confirmacao/',
            accounts_views.resend_email_verification,
            name='resend_email_verification',
        ),
        path(
            'confirmar-email/<str:token>/',
            accounts_views.confirm_email,
            name='confirm_email',
        ),
        path('sair/', accounts_views.logout, name='logout'),
        path('excluir-conta/', accounts_views.delete_account, name='delete_account'),
    ],
    'accounts',
)


urlpatterns = [
    path('', showcase_views.home, name='home'),
    path('sitemap.xml', seo.sitemap_xml, name='sitemap'),
    path('robots.txt', seo.robots_txt, name='robots'),
    path('llms.txt', seo.llms_txt, name='llms'),
    path(
        'admin/painel',
        RedirectView.as_view(pattern_name='dashboard:home', permanent=False),
        name='legacy_admin_panel',
    ),
    path(
        'admin/painel/',
        RedirectView.as_view(pattern_name='dashboard:home', permanent=False),
    ),
    path(
        'admin/logout/',
        LogoutView.as_view(next_page='admin:login'),
        name='admin_logout',
    ),
    path('admin/', admin.site.urls),
    path('produtos/', include('products.urls')),
    path('servicos/', include('glazing_services.urls')),
    path('painel/calculadora/', include('calculator.urls')),
    path('painel/vendas/', include('sales.urls')),
    path('', include('dashboard.urls')),
    path('', include(accounts_patterns, namespace='accounts')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
