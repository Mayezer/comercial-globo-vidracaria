from django.conf import settings
from django.http import HttpResponse
from django.utils.cache import patch_vary_headers


class SecurityHeadersMiddleware:
    """Add browser protections that are not included in Django's defaults."""

    CONTENT_SECURITY_POLICY = (
        "default-src 'self'; "
        "base-uri 'self'; "
        "connect-src 'self'; "
        "font-src 'self' data: https://cdn.jsdelivr.net https://fonts.gstatic.com; "
        "form-action 'self'; "
        "frame-ancestors 'none'; "
        "img-src 'self' data:; "
        "object-src 'none'; "
        "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
        "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://fonts.googleapis.com; "
        "upgrade-insecure-requests"
    )

    PERMISSIONS_POLICY = (
        'accelerometer=(), autoplay=(), camera=(), geolocation=(), '
        'gyroscope=(), magnetometer=(), microphone=(), payment=(), usb=()'
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response.headers.setdefault('Content-Security-Policy', self.CONTENT_SECURITY_POLICY)
        response.headers.setdefault('Permissions-Policy', self.PERMISSIONS_POLICY)
        response.headers.setdefault('Cross-Origin-Resource-Policy', 'same-origin')
        return response


class RestrictedCORSMiddleware:
    """Optionally expose only public, read-only pages to configured origins."""

    PUBLIC_PATHS = frozenset({'/', '/robots.txt', '/sitemap.xml', '/llms.txt'})
    PUBLIC_PREFIXES = ('/produtos/', '/servicos/')
    ALLOWED_METHODS = 'GET, HEAD, OPTIONS'
    ALLOWED_HEADERS = 'Accept, Content-Type'

    def __init__(self, get_response):
        self.get_response = get_response

    @classmethod
    def is_public_path(cls, path):
        return path in cls.PUBLIC_PATHS or path.startswith(cls.PUBLIC_PREFIXES)

    def __call__(self, request):
        origin = request.headers.get('Origin')
        allowed = (
            origin
            and origin in settings.CORS_ALLOWED_ORIGINS
            and self.is_public_path(request.path)
        )

        if allowed and request.method == 'OPTIONS':
            requested_method = request.headers.get('Access-Control-Request-Method', '')
            if requested_method not in {'GET', 'HEAD'}:
                return HttpResponse(status=405)
            response = HttpResponse(status=204)
        else:
            response = self.get_response(request)

        if allowed and request.method in {'GET', 'HEAD', 'OPTIONS'}:
            response.headers['Access-Control-Allow-Origin'] = origin
            response.headers['Access-Control-Allow-Methods'] = self.ALLOWED_METHODS
            response.headers['Access-Control-Allow-Headers'] = self.ALLOWED_HEADERS
            response.headers['Access-Control-Max-Age'] = '600'
            response.headers['Cross-Origin-Resource-Policy'] = 'cross-origin'
            patch_vary_headers(response, ('Origin',))
        return response
