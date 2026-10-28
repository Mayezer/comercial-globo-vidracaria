import mimetypes
import os
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit
from urllib.request import Request, urlopen

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import Storage
from django.utils.deconstruct import deconstructible


@deconstructible
class R2WorkerStorage(Storage):
    """Store user uploads through the Container's private R2 outbound handler."""

    def __init__(self, endpoint=None, timeout=30):
        self.endpoint = (endpoint or os.environ.get('MEDIA_STORAGE_ENDPOINT', '')).rstrip('/')
        self.timeout = timeout
        if not self.endpoint:
            raise ValueError('Defina MEDIA_STORAGE_ENDPOINT para usar R2WorkerStorage.')
        parsed_endpoint = urlsplit(self.endpoint)
        if (
            parsed_endpoint.scheme != 'http'
            or parsed_endpoint.hostname != 'media.internal'
            or parsed_endpoint.port is not None
            or parsed_endpoint.username is not None
            or parsed_endpoint.password is not None
            or parsed_endpoint.path not in {'', '/'}
            or parsed_endpoint.query
            or parsed_endpoint.fragment
        ):
            raise ValueError('MEDIA_STORAGE_ENDPOINT deve ser exatamente http://media.internal.')

    def _url_for_name(self, name):
        return f"{self.endpoint}/{quote(name, safe='/')}"

    def _request(self, method, name, data=None, headers=None):
        request = Request(
            self._url_for_name(name),
            data=data,
            headers=headers or {},
            method=method,
        )
        try:
            # The constructor restricts requests to the Worker's private virtual host.
            with urlopen(request, timeout=self.timeout) as response:  # nosec B310
                return response.status, response.headers, response.read()
        except HTTPError as error:
            if error.code == 404:
                return error.code, error.headers, b''
            raise OSError(f'Falha no armazenamento de mídia (HTTP {error.code}).') from error
        except URLError as error:
            raise OSError('Não foi possível acessar o armazenamento de mídia.') from error

    def _open(self, name, mode='rb'):
        if mode not in {'r', 'rb'}:
            raise ValueError('R2WorkerStorage permite abrir arquivos apenas para leitura.')
        status, _, body = self._request('GET', name)
        if status == 404:
            raise FileNotFoundError(name)
        return ContentFile(body, name=name)

    def _save(self, name, content):
        content.open()
        body = content.read()
        if isinstance(body, str):
            body = body.encode()
        content_type = mimetypes.guess_type(name)[0] or 'application/octet-stream'
        self._request('PUT', name, data=body, headers={'Content-Type': content_type})
        return name

    def delete(self, name):
        self._request('DELETE', name)

    def exists(self, name):
        status, _, _ = self._request('HEAD', name)
        return status == 200

    def size(self, name):
        status, headers, _ = self._request('HEAD', name)
        if status == 404:
            raise FileNotFoundError(name)
        return int(headers.get('Content-Length', '0'))

    def url(self, name):
        return f"{settings.MEDIA_URL.rstrip('/')}/{quote(name, safe='/')}"
