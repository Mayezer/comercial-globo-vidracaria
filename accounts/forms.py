import uuid

from django import forms
from django.contrib.admin.forms import AdminAuthenticationForm
from django.contrib.auth import authenticate, get_user_model, password_validation
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from app.crypto import blind_index

from .models import AuthenticationThrottle, Profile, only_digits, validate_cnpj, validate_cpf
from .security import (
    GENERIC_LOGIN_ERROR,
    login_attempt_allowed,
    record_login_failure,
    record_login_success,
)


User = get_user_model()


class AccountCreationForm(forms.Form):
    account_type = forms.ChoiceField(
        label='Tipo de pessoa',
        choices=Profile.AccountType.choices,
        widget=forms.RadioSelect(attrs={'class': 'radio-list'}),
    )
    document = forms.CharField(
        label='CPF ou CNPJ',
        max_length=18,
        widget=forms.TextInput(attrs={'inputmode': 'numeric'}),
    )
    email = forms.EmailField(
        label='E-mail para confirmação',
        help_text='O acesso à conta será feito com seu CPF ou CNPJ.',
    )
    password = forms.CharField(label='Senha', strip=False, widget=forms.PasswordInput)
    password_confirmation = forms.CharField(
        label='Confirmar senha',
        strip=False,
        widget=forms.PasswordInput,
    )

    def __init__(self, *args, **kwargs):
        self.identity_conflict = False
        super().__init__(*args, **kwargs)

    def clean_document(self):
        document = only_digits(self.cleaned_data['document'])
        account_type = self.data.get('account_type')

        if account_type == Profile.AccountType.INDIVIDUAL:
            validate_cpf(document)
        elif account_type == Profile.AccountType.COMPANY:
            validate_cnpj(document)

        if Profile.objects.filter(
            document_hash=blind_index(document, 'profile.document')
        ).exists():
            self.identity_conflict = True
        return document

    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()
        if Profile.objects.filter(email_hash=blind_index(email, 'profile.email')).exists():
            self.identity_conflict = True
        return email

    def clean_password(self):
        password = self.cleaned_data['password']
        candidate = User(
            username=only_digits(self.data.get('document', '')),
            email=self.data.get('email', '').strip().lower(),
        )
        password_validation.validate_password(password, candidate)
        return password

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        password_confirmation = cleaned_data.get('password_confirmation')

        if password and password_confirmation and password != password_confirmation:
            self.add_error('password_confirmation', 'As senhas não coincidem.')
        return cleaned_data

    @transaction.atomic
    def save(self):
        if self.identity_conflict:
            User().set_password(self.cleaned_data['password'])
            return None
        try:
            with transaction.atomic():
                user = User.objects.create_user(
                    username=f'acct_{uuid.uuid4().hex}',
                    email='',
                    password=self.cleaned_data['password'],
                )
                Profile.objects.create(
                    user=user,
                    account_type=self.cleaned_data['account_type'],
                    document=self.cleaned_data['document'],
                    email=self.cleaned_data['email'],
                )
                return user
        except IntegrityError:
            User().set_password(self.cleaned_data['password'])
            return None


class LoginForm(forms.Form):
    identifier = forms.CharField(label='CPF ou CNPJ', max_length=150)
    password = forms.CharField(label='Senha', strip=False, widget=forms.PasswordInput)

    def __init__(self, request=None, *args, **kwargs):
        self.request = request
        self.user = None
        super().__init__(*args, **kwargs)

    def clean_identifier(self):
        identifier = self.cleaned_data['identifier'].strip()
        if '@' in identifier:
            raise ValidationError('E-mail não é aceito no login. Use seu CPF ou CNPJ.')
        return identifier

    def clean(self):
        cleaned_data = super().clean()
        identifier = cleaned_data.get('identifier')
        password = cleaned_data.get('password')

        if identifier and password:
            scope = AuthenticationThrottle.Scope.CUSTOMER
            if not login_attempt_allowed(identifier, scope):
                User().set_password(password)
                raise ValidationError(GENERIC_LOGIN_ERROR)
            self.user = authenticate(self.request, username=identifier, password=password)
            if self.user is None:
                record_login_failure(identifier, scope)
                raise ValidationError(GENERIC_LOGIN_ERROR)
            record_login_success(identifier, scope)
        return cleaned_data


class ProtectedAdminAuthenticationForm(AdminAuthenticationForm):
    error_messages = {
        **AdminAuthenticationForm.error_messages,
        'invalid_login': GENERIC_LOGIN_ERROR,
    }

    def clean(self):
        identifier = self.data.get('username', '')
        password = self.data.get('password', '')
        scope = AuthenticationThrottle.Scope.ADMIN
        if identifier and password and not login_attempt_allowed(identifier, scope):
            User().set_password(password)
            raise ValidationError(GENERIC_LOGIN_ERROR, code='invalid_login')
        try:
            cleaned_data = super().clean()
        except ValidationError as error:
            if identifier and password:
                record_login_failure(identifier, scope)
            raise ValidationError(GENERIC_LOGIN_ERROR, code='invalid_login') from error
        if identifier and password:
            record_login_success(identifier, scope)
        return cleaned_data


class ProfileForm(forms.ModelForm):
    phone = forms.CharField(
        label='Telefone',
        max_length=17,
        required=False,
        widget=forms.TextInput(
            attrs={
                'inputmode': 'numeric',
                'placeholder': '(00) 00000 - 0000',
            }
        ),
    )

    class Meta:
        model = Profile
        fields = (
            'full_name',
            'corporate_name',
            'street',
            'neighborhood',
            'house_number',
            'reference_point',
            'profile_photo',
            'phone',
        )
        widgets = {
            'profile_photo': forms.FileInput(attrs={'accept': 'image/jpeg,image/png,image/webp'}),
        }

    def __init__(self, *args, require_address=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.require_address = require_address
        if require_address:
            for field_name in ('street', 'neighborhood', 'house_number'):
                self.fields[field_name].required = True

    def clean_phone(self):
        phone = only_digits(self.cleaned_data.get('phone', ''))
        if phone and len(phone) != 11:
            raise ValidationError('Informe um telefone com DDD no padrão (00) 00000 - 0000.')
        return phone

    def clean(self):
        cleaned_data = super().clean()
        if self.instance.account_type == Profile.AccountType.INDIVIDUAL:
            cleaned_data['corporate_name'] = ''
        return cleaned_data
