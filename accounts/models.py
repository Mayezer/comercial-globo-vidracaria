import re

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from app.validators import validate_image_upload
from app.crypto import EncryptedEmailField, EncryptedTextField, blind_index


def only_digits(value):
    return re.sub(r'\D', '', value or '')


def normalize_text(value):
    return ' '.join((value or '').strip().casefold().split())


def validate_cpf(value):
    cpf = only_digits(value)
    if len(cpf) != 11 or cpf == cpf[0] * 11:
        raise ValidationError('Informe um CPF válido.')

    first_digit = (sum(int(cpf[index]) * (10 - index) for index in range(9)) * 10) % 11
    first_digit = 0 if first_digit == 10 else first_digit
    second_digit = (sum(int(cpf[index]) * (11 - index) for index in range(10)) * 10) % 11
    second_digit = 0 if second_digit == 10 else second_digit

    if cpf[-2:] != f'{first_digit}{second_digit}':
        raise ValidationError('Informe um CPF válido.')


def validate_cnpj(value):
    cnpj = only_digits(value)
    if len(cnpj) != 14 or cnpj == cnpj[0] * 14:
        raise ValidationError('Informe um CNPJ válido.')

    def calculate_digit(numbers, weights):
        remainder = sum(int(number) * weight for number, weight in zip(numbers, weights)) % 11
        return 0 if remainder < 2 else 11 - remainder

    first_digit = calculate_digit(cnpj[:12], [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2])
    second_digit = calculate_digit(cnpj[:12] + str(first_digit), [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2])

    if cnpj[-2:] != f'{first_digit}{second_digit}':
        raise ValidationError('Informe um CNPJ válido.')


class Profile(models.Model):
    class AccountType(models.TextChoices):
        INDIVIDUAL = 'PF', 'Pessoa física'
        COMPANY = 'PJ', 'Pessoa jurídica'

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='profile',
    )
    account_type = models.CharField('tipo de pessoa', max_length=2, choices=AccountType.choices)
    document = EncryptedTextField('CPF ou CNPJ', max_length=14)
    document_hash = models.CharField(max_length=64, unique=True, editable=False)
    email = EncryptedEmailField('e-mail', max_length=254)
    email_hash = models.CharField(max_length=64, unique=True, editable=False)
    email_verified_at = models.DateTimeField('e-mail confirmado em', null=True, blank=True)
    full_name = EncryptedTextField('nome completo', max_length=150, blank=True)
    full_name_hash = models.CharField(
        max_length=64, blank=True, default='', db_index=True, editable=False
    )
    corporate_name = EncryptedTextField('razão social', max_length=180, blank=True)
    corporate_name_hash = models.CharField(
        max_length=64, blank=True, default='', db_index=True, editable=False
    )
    street = EncryptedTextField('rua', max_length=150, blank=True)
    neighborhood = EncryptedTextField('bairro', max_length=100, blank=True)
    house_number = EncryptedTextField('número', max_length=20, blank=True)
    reference_point = EncryptedTextField('ponto de referência', max_length=180, blank=True)
    profile_photo = models.FileField(
        'foto de perfil',
        upload_to='profile_photos/',
        blank=True,
        validators=[validate_image_upload],
    )
    phone = EncryptedTextField('telefone', max_length=13, blank=True)
    phone_hash = models.CharField(
        max_length=64, blank=True, default='', db_index=True, editable=False
    )

    class Meta:
        verbose_name = 'perfil'
        verbose_name_plural = 'perfis'

    def clean(self):
        super().clean()
        self.document = only_digits(self.document)
        self.email = self.email.strip().lower()

        if self.account_type == self.AccountType.INDIVIDUAL:
            validate_cpf(self.document)
            self.corporate_name = ''
        elif self.account_type == self.AccountType.COMPANY:
            validate_cnpj(self.document)

    def save(self, *args, **kwargs):
        self.document = only_digits(self.document)
        self.email = self.email.strip().lower()
        self.full_name = (self.full_name or '').strip()
        self.corporate_name = (self.corporate_name or '').strip()
        self.phone = only_digits(self.phone)
        self.document_hash = blind_index(self.document, 'profile.document')
        self.email_hash = blind_index(self.email, 'profile.email')
        self.full_name_hash = blind_index(normalize_text(self.full_name), 'profile.full_name')
        self.corporate_name_hash = blind_index(
            normalize_text(self.corporate_name),
            'profile.corporate_name',
        )
        self.phone_hash = blind_index(self.phone, 'profile.phone')
        update_fields = kwargs.get('update_fields')
        if update_fields:
            related_hashes = {
                'document': 'document_hash',
                'email': 'email_hash',
                'full_name': 'full_name_hash',
                'corporate_name': 'corporate_name_hash',
                'phone': 'phone_hash',
            }
            expanded = set(update_fields)
            expanded.update(
                hash_field for source, hash_field in related_hashes.items() if source in expanded
            )
            kwargs['update_fields'] = tuple(expanded)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.full_name or self.corporate_name or self.email

    @property
    def is_email_verified(self):
        return self.email_verified_at is not None

    def verify_email(self):
        if not self.email_verified_at:
            self.email_verified_at = timezone.now()
            self.save(update_fields=['email_verified_at'])

    @property
    def formatted_document(self):
        if self.account_type == self.AccountType.INDIVIDUAL and len(self.document) == 11:
            return f'{self.document[:3]}.{self.document[3:6]}.{self.document[6:9]}-{self.document[9:]}'
        if self.account_type == self.AccountType.COMPANY and len(self.document) == 14:
            return (
                f'{self.document[:2]}.{self.document[2:5]}.{self.document[5:8]}/'
                f'{self.document[8:12]}-{self.document[12:]}'
            )
        return self.document

    @property
    def masked_document(self):
        if len(self.document) == 11:
            return f'***.{self.document[3:6]}.{self.document[6:9]}-**'
        if len(self.document) == 14:
            return f'**.{self.document[2:5]}.{self.document[5:8]}/****-**'
        return 'Documento protegido'

    @property
    def formatted_phone(self):
        if len(self.phone) == 11:
            return f'({self.phone[:2]}) {self.phone[2:7]} - {self.phone[7:]}'
        return self.phone

    @property
    def has_complete_address(self):
        return all(
            value and value.strip()
            for value in (self.street, self.neighborhood, self.house_number)
        )


class AuthenticationThrottle(models.Model):
    class Scope(models.TextChoices):
        CUSTOMER = 'customer', 'Login de cliente'
        ADMIN = 'admin', 'Login administrativo'

    scope = models.CharField(max_length=12, choices=Scope.choices)
    identifier_digest = models.CharField(max_length=64)
    failed_attempts = models.PositiveIntegerField(default=0)
    blocked_until = models.DateTimeField(null=True, blank=True)
    last_failed_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=('scope', 'identifier_digest'),
                name='unique_auth_throttle_scope_identifier',
            ),
        ]
        indexes = [models.Index(fields=('blocked_until',), name='auth_blocked_until_idx')]

    def __str__(self):
        return f'{self.scope}:{self.identifier_digest[:12]}'
