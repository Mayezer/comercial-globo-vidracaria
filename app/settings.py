import os
import secrets
from pathlib import Path
from urllib.parse import parse_qsl, unquote, urlsplit

from django.core.exceptions import ImproperlyConfigured

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


def env_bool(name, default=False):
    return os.environ.get(name, str(default)).strip().lower() in {'1', 'true', 'yes', 'on'}


def env_list(name, default=''):
    return [value.strip() for value in os.environ.get(name, default).split(',') if value.strip()]


DEBUG = env_bool('DJANGO_DEBUG', True)
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', '').strip()
if not SECRET_KEY:
    if not DEBUG:
        raise ImproperlyConfigured('Defina DJANGO_SECRET_KEY quando DJANGO_DEBUG=False.')
    SECRET_KEY = secrets.token_urlsafe(50)

ALLOWED_HOSTS = env_list('DJANGO_ALLOWED_HOSTS', 'localhost,127.0.0.1')
PUBLIC_SITE_URL = os.environ.get(
    'PUBLIC_SITE_URL',
    'https://comercial-globo-vidracaria-e-construcao.mayezer.com',
).strip().rstrip('/')
parsed_public_site_url = urlsplit(PUBLIC_SITE_URL)
if (
    parsed_public_site_url.scheme != 'https'
    or not parsed_public_site_url.netloc
    or parsed_public_site_url.path not in {'', '/'}
):
    raise ImproperlyConfigured('PUBLIC_SITE_URL deve ser uma origem HTTPS sem caminho.')
CSRF_TRUSTED_ORIGINS = env_list(
    'DJANGO_CSRF_TRUSTED_ORIGINS',
    PUBLIC_SITE_URL,
)
CORS_ALLOWED_ORIGINS = env_list('CORS_ALLOWED_ORIGINS')
if '*' in CORS_ALLOWED_ORIGINS:
    raise ImproperlyConfigured('CORS_ALLOWED_ORIGINS não aceita wildcard.')
GOOGLE_SITE_VERIFICATION = os.environ.get('GOOGLE_SITE_VERIFICATION', '').strip()
FIELD_ENCRYPTION_KEYS = os.environ.get('FIELD_ENCRYPTION_KEYS', '').strip()
FIELD_ENCRYPTION_ACTIVE_KEY = os.environ.get('FIELD_ENCRYPTION_ACTIVE_KEY', 'v1').strip()
FIELD_HASH_KEY = os.environ.get('FIELD_HASH_KEY', '').strip()
if not DEBUG and (not FIELD_ENCRYPTION_KEYS or not FIELD_HASH_KEY):
    raise ImproperlyConfigured(
        'Defina FIELD_ENCRYPTION_KEYS e FIELD_HASH_KEY quando DJANGO_DEBUG=False.'
    )

AUTH_LOCKOUT_THRESHOLD = int(os.environ.get('AUTH_LOCKOUT_THRESHOLD', '5'))
AUTH_LOCKOUT_BASE_SECONDS = int(os.environ.get('AUTH_LOCKOUT_BASE_SECONDS', '30'))
AUTH_LOCKOUT_MAX_SECONDS = int(os.environ.get('AUTH_LOCKOUT_MAX_SECONDS', '900'))
AUTH_LOCKOUT_RESET_SECONDS = int(os.environ.get('AUTH_LOCKOUT_RESET_SECONDS', '3600'))


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'accounts',
    'categories.apps.CategoriesConfig',
    'products.apps.ProductsConfig',
    'glazing_services.apps.GlazingServicesConfig',
    'calculator.apps.CalculatorConfig',
    'showcase',
    'dashboard.apps.DashboardConfig',
    'sales.apps.SalesConfig',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'app.middleware.SecurityHeadersMiddleware',
    'app.middleware.RestrictedCORSMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'app.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'app.context_processors.public_site',
            ],
        },
    },
]

WSGI_APPLICATION = 'app.wsgi.application'


# Database
# https://docs.djangoproject.com/en/5.2/ref/settings/#databases

DATABASE_URL = os.environ.get('DATABASE_URL', '').strip()

if DATABASE_URL:
    parsed_database_url = urlsplit(DATABASE_URL)
    if parsed_database_url.scheme not in {'postgres', 'postgresql'}:
        raise ImproperlyConfigured('DATABASE_URL deve usar o esquema postgres:// ou postgresql://.')
    if not parsed_database_url.hostname or not parsed_database_url.path.strip('/'):
        raise ImproperlyConfigured('DATABASE_URL deve informar host e nome do banco.')

    database_options = dict(parse_qsl(parsed_database_url.query))
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': unquote(parsed_database_url.path.lstrip('/')),
            'USER': unquote(parsed_database_url.username or ''),
            'PASSWORD': unquote(parsed_database_url.password or ''),
            'HOST': parsed_database_url.hostname,
            'PORT': parsed_database_url.port or 5432,
            'CONN_MAX_AGE': int(os.environ.get('POSTGRES_CONN_MAX_AGE', '60')),
            'CONN_HEALTH_CHECKS': True,
            'OPTIONS': database_options,
        },
    }
elif os.environ.get('DATABASE_ENGINE', 'postgresql').strip().lower() == 'sqlite':
    # Alternativa explícita para testes rápidos sem um servidor PostgreSQL.
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': os.environ.get('SQLITE_NAME', BASE_DIR / 'db.sqlite3'),
        },
    }
else:
    postgres_password = os.environ.get('POSTGRES_PASSWORD', '').strip()
    if not DEBUG and not postgres_password:
        raise ImproperlyConfigured('Defina POSTGRES_PASSWORD ou DATABASE_URL em produção.')
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': os.environ.get('POSTGRES_DB', 'globo_vidracaria'),
            'USER': os.environ.get('POSTGRES_USER', 'globo_vidracaria'),
            'PASSWORD': postgres_password,
            'HOST': os.environ.get('POSTGRES_HOST', '127.0.0.1'),
            'PORT': os.environ.get('POSTGRES_PORT', '5432'),
            'CONN_MAX_AGE': int(os.environ.get('POSTGRES_CONN_MAX_AGE', '60')),
            'CONN_HEALTH_CHECKS': True,
        },
    }


# Password validation
# https://docs.djangoproject.com/en/5.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/5.2/topics/i18n/

LANGUAGE_CODE = 'pt-br'

TIME_ZONE = 'America/Sao_Paulo'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.2/howto/static-files/

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

STORAGES = {
    'default': {
        'BACKEND': 'django.core.files.storage.FileSystemStorage',
    },
    'staticfiles': {
        'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage',
    },
}

if os.environ.get('MEDIA_STORAGE_ENDPOINT', '').strip():
    STORAGES['default'] = {
        'BACKEND': 'app.storage.R2WorkerStorage',
    }

AUTHENTICATION_BACKENDS = [
    'accounts.backends.DocumentBackend',
    'django.contrib.auth.backends.ModelBackend',
]

LOGIN_URL = 'accounts:login'

EMAIL_BACKEND = os.environ.get(
    'EMAIL_BACKEND',
    'django.core.mail.backends.console.EmailBackend',
)
EMAIL_DELIVERY_ENABLED = env_bool('EMAIL_DELIVERY_ENABLED', DEBUG)
EMAIL_HOST = os.environ.get('EMAIL_HOST', '')
EMAIL_PORT = int(os.environ.get('EMAIL_PORT', '587'))
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')
EMAIL_USE_TLS = env_bool('EMAIL_USE_TLS', True)
EMAIL_TIMEOUT = int(os.environ.get('EMAIL_TIMEOUT', '10'))
DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', 'nao-responda@vidracariaglobo.local')

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'redacted': {
            '()': 'app.logging.RedactingFormatter',
            'format': '{levelname} {name} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'redacted',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': os.environ.get('DJANGO_LOG_LEVEL', 'WARNING'),
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': os.environ.get('DJANGO_LOG_LEVEL', 'INFO'),
            'propagate': False,
        },
        'django.server': {
            'handlers': ['console'],
            'level': os.environ.get('DJANGO_LOG_LEVEL', 'INFO'),
            'propagate': False,
        },
        'gunicorn.error': {
            'handlers': ['console'],
            'level': os.environ.get('DJANGO_LOG_LEVEL', 'INFO'),
            'propagate': False,
        },
    },
}

SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
USE_X_FORWARDED_HOST = True
SECURE_SSL_REDIRECT = env_bool('DJANGO_SECURE_SSL_REDIRECT', not DEBUG)
SESSION_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SAMESITE = 'Lax'
SECURE_HSTS_SECONDS = int(os.environ.get('DJANGO_SECURE_HSTS_SECONDS', '31536000' if not DEBUG else '0'))
SECURE_HSTS_INCLUDE_SUBDOMAINS = not DEBUG
SECURE_HSTS_PRELOAD = not DEBUG
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = 'same-origin'
SECURE_CROSS_ORIGIN_OPENER_POLICY = 'same-origin'
X_FRAME_OPTIONS = 'DENY'

DATA_UPLOAD_MAX_MEMORY_SIZE = 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 1024 * 1024

# Default primary key field type
# https://docs.djangoproject.com/en/5.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
