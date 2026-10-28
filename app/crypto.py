import base64
import hashlib
import hmac
import os
from decimal import Decimal, InvalidOperation

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from django import forms
from django.conf import settings
from django.core import validators
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.db import models


ENCRYPTED_PREFIX = 'enc$'


class SensitiveDataError(ValidationError):
    """Raised without echoing a damaged ciphertext or secret key."""


def _decode_secret(value, setting_name):
    try:
        padded = value + ('=' * (-len(value) % 4))
        decoded = base64.urlsafe_b64decode(padded.encode('ascii'))
    except (ValueError, UnicodeError) as error:
        raise ImproperlyConfigured(f'{setting_name} deve usar Base64 URL-safe.') from error
    if len(decoded) != 32:
        raise ImproperlyConfigured(f'{setting_name} deve representar exatamente 32 bytes.')
    return decoded


def encryption_keys():
    configured = getattr(settings, 'FIELD_ENCRYPTION_KEYS', '')
    keys = {}
    for item in configured.split(','):
        item = item.strip()
        if not item:
            continue
        try:
            version, encoded_key = item.split(':', 1)
        except ValueError as error:
            raise ImproperlyConfigured(
                'FIELD_ENCRYPTION_KEYS deve usar o formato versão:chave_base64.'
            ) from error
        version = version.strip()
        if not version or '$' in version or version in keys:
            raise ImproperlyConfigured('FIELD_ENCRYPTION_KEYS contém uma versão inválida ou repetida.')
        keys[version] = _decode_secret(encoded_key.strip(), 'FIELD_ENCRYPTION_KEYS')
    return keys


def active_encryption_key():
    version = getattr(settings, 'FIELD_ENCRYPTION_ACTIVE_KEY', '').strip()
    keys = encryption_keys()
    if not version or version not in keys:
        raise ImproperlyConfigured(
            'FIELD_ENCRYPTION_ACTIVE_KEY deve indicar uma versão presente em FIELD_ENCRYPTION_KEYS.'
        )
    return version, keys[version]


def encrypt_value(value, context):
    if value in (None, ''):
        return '' if value == '' else None
    if isinstance(value, str) and value.startswith(ENCRYPTED_PREFIX):
        return value
    version, key = active_encryption_key()
    nonce = os.urandom(12)
    ciphertext = AESGCM(key).encrypt(nonce, str(value).encode('utf-8'), context.encode('utf-8'))
    encoded_nonce = base64.urlsafe_b64encode(nonce).decode('ascii').rstrip('=')
    encoded_ciphertext = base64.urlsafe_b64encode(ciphertext).decode('ascii').rstrip('=')
    return f'{ENCRYPTED_PREFIX}{version}${encoded_nonce}${encoded_ciphertext}'


def decrypt_value(value, context):
    if value in (None, ''):
        return '' if value == '' else None
    if not isinstance(value, str) or not value.startswith(ENCRYPTED_PREFIX):
        # Permite uma implantação em duas etapas e a migração segura dos dados legados.
        return value
    try:
        _, version, encoded_nonce, encoded_ciphertext = value.split('$', 3)
        key = encryption_keys()[version]
        nonce = base64.urlsafe_b64decode(encoded_nonce + ('=' * (-len(encoded_nonce) % 4)))
        ciphertext = base64.urlsafe_b64decode(
            encoded_ciphertext + ('=' * (-len(encoded_ciphertext) % 4))
        )
        plaintext = AESGCM(key).decrypt(nonce, ciphertext, context.encode('utf-8'))
        return plaintext.decode('utf-8')
    except (KeyError, ValueError, UnicodeError, InvalidTag) as error:
        raise SensitiveDataError('Não foi possível validar o dado protegido.') from error


def hash_key():
    configured = getattr(settings, 'FIELD_HASH_KEY', '').strip()
    if not configured:
        raise ImproperlyConfigured('Defina FIELD_HASH_KEY para comparar dados protegidos.')
    return _decode_secret(configured, 'FIELD_HASH_KEY')


def blind_index(value, purpose):
    if value in (None, ''):
        return ''
    message = f'{purpose}\0{value}'.encode('utf-8')
    return hmac.new(hash_key(), message, hashlib.sha256).hexdigest()


def matches_blind_index(value, expected_digest, purpose):
    return hmac.compare_digest(blind_index(value, purpose), expected_digest or '')


class EncryptedTextField(models.TextField):
    def __init__(self, *args, text_area=False, **kwargs):
        self.text_area = text_area
        super().__init__(*args, **kwargs)

    def deconstruct(self):
        name, path, args, kwargs = super().deconstruct()
        if self.text_area:
            kwargs['text_area'] = True
        return name, path, args, kwargs

    def contribute_to_class(self, cls, name, private_only=False):
        super().contribute_to_class(cls, name, private_only=private_only)
        self.crypto_context = f'{cls._meta.label_lower}.{name}'

    def from_db_value(self, value, expression, connection):
        return decrypt_value(value, self.crypto_context)

    def to_python(self, value):
        return decrypt_value(value, self.crypto_context)

    def get_prep_value(self, value):
        return encrypt_value(value, self.crypto_context)

    def formfield(self, **kwargs):
        defaults = {
            'form_class': forms.CharField,
            'widget': forms.Textarea if self.text_area else forms.TextInput,
        }
        defaults.update(kwargs)
        return super().formfield(**defaults)


class EncryptedEmailField(EncryptedTextField):
    default_validators = [validators.validate_email]
    description = 'Endereço de e-mail protegido com criptografia autenticada'

    def formfield(self, **kwargs):
        defaults = {'form_class': forms.EmailField, 'widget': forms.EmailInput}
        defaults.update(kwargs)
        return super().formfield(**defaults)


class EncryptedDecimalField(EncryptedTextField):
    def __init__(self, *args, max_digits=None, decimal_places=None, **kwargs):
        self.max_digits = max_digits
        self.decimal_places = decimal_places
        super().__init__(*args, **kwargs)

    def deconstruct(self):
        name, path, args, kwargs = super().deconstruct()
        kwargs['max_digits'] = self.max_digits
        kwargs['decimal_places'] = self.decimal_places
        return name, path, args, kwargs

    def from_db_value(self, value, expression, connection):
        value = super().from_db_value(value, expression, connection)
        return self.to_decimal(value)

    def to_python(self, value):
        value = super().to_python(value)
        return self.to_decimal(value)

    @staticmethod
    def to_decimal(value):
        if value in (None, '') or isinstance(value, Decimal):
            return value
        try:
            return Decimal(value)
        except (InvalidOperation, TypeError, ValueError) as error:
            raise ValidationError('Informe um valor decimal válido.') from error

    def get_prep_value(self, value):
        decimal_value = self.to_decimal(value)
        if decimal_value in (None, ''):
            return super().get_prep_value(decimal_value)
        return encrypt_value(format(decimal_value, 'f'), self.crypto_context)

    def formfield(self, **kwargs):
        defaults = {
            'form_class': forms.DecimalField,
            'max_digits': self.max_digits,
            'decimal_places': self.decimal_places,
        }
        defaults.update(kwargs)
        return models.Field.formfield(self, **defaults)
