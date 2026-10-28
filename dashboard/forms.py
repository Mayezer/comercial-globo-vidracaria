from decimal import Decimal
import uuid

from django import forms
from django.contrib.auth import get_user_model, password_validation
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q

from accounts.models import Profile, only_digits, validate_cnpj, validate_cpf
from app.crypto import blind_index
from categories.models import Category
from products.models import Product
from glazing_services.models import Service

from .models import (
    CashTransaction,
    Employee,
    Expense,
    Payroll,
    QuoteRequest,
    Supplier,
    SystemSettings,
)


User = get_user_model()


class BrazilianDecimalField(forms.DecimalField):
    def to_python(self, value):
        if isinstance(value, str) and ',' in value:
            value = value.strip().replace('.', '').replace(',', '.')
        return super().to_python(value)


class AdministratorCreationForm(forms.ModelForm):
    password = forms.CharField(
        label='Senha',
        strip=False,
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}),
    )
    password_confirmation = forms.CharField(
        label='Confirmar senha',
        strip=False,
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}),
    )

    class Meta:
        model = User
        fields = ('username', 'first_name', 'last_name', 'email')
        labels = {
            'username': 'Usuário',
            'first_name': 'Nome',
            'last_name': 'Sobrenome',
            'email': 'E-mail',
        }
        help_texts = {
            'username': 'Use letras, números e os caracteres @, ., +, - ou _.',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['email'].required = True
        self.order_fields(
            ('first_name', 'last_name', 'username', 'email', 'password', 'password_confirmation')
        )

    def clean_username(self):
        username = self.cleaned_data['username'].strip()
        if User.objects.filter(username__iexact=username).exists():
            raise ValidationError('Já existe uma conta com este nome de usuário.')
        return username

    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError('Já existe uma conta com este e-mail.')
        return email

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        password_confirmation = cleaned_data.get('password_confirmation')

        if password and password_confirmation and password != password_confirmation:
            self.add_error('password_confirmation', 'As senhas não coincidem.')
        elif password:
            candidate = User(
                username=cleaned_data.get('username', ''),
                email=cleaned_data.get('email', ''),
                first_name=cleaned_data.get('first_name', ''),
                last_name=cleaned_data.get('last_name', ''),
            )
            try:
                password_validation.validate_password(password, candidate)
            except ValidationError as error:
                self.add_error('password', error)
        return cleaned_data

    @transaction.atomic
    def save(self, commit=True):
        administrator = super().save(commit=False)
        administrator.email = self.cleaned_data['email']
        administrator.is_active = True
        administrator.is_staff = True
        administrator.is_superuser = False
        administrator.set_password(self.cleaned_data['password'])
        if commit:
            administrator.save()
        return administrator


class AdministratorUpdateForm(forms.ModelForm):
    is_active = forms.BooleanField(label='Conta ativa', required=False)
    password = forms.CharField(
        label='Nova senha',
        strip=False,
        required=False,
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}),
        help_text='Deixe em branco para manter a senha atual.',
    )
    password_confirmation = forms.CharField(
        label='Confirmar nova senha',
        strip=False,
        required=False,
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}),
    )

    class Meta:
        model = User
        fields = ('username', 'first_name', 'last_name', 'email', 'is_active')
        labels = {
            'username': 'Usuário',
            'first_name': 'Nome',
            'last_name': 'Sobrenome',
            'email': 'E-mail',
        }
        help_texts = {
            'username': 'Use letras, números e os caracteres @, ., +, - ou _.',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['email'].required = True
        self.order_fields(
            (
                'first_name',
                'last_name',
                'username',
                'email',
                'is_active',
                'password',
                'password_confirmation',
            )
        )

    def clean_username(self):
        username = self.cleaned_data['username'].strip()
        duplicate = User.objects.filter(username__iexact=username).exclude(pk=self.instance.pk)
        if duplicate.exists():
            raise ValidationError('Já existe uma conta com este nome de usuário.')
        return username

    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()
        duplicate = User.objects.filter(email__iexact=email).exclude(pk=self.instance.pk)
        if duplicate.exists():
            raise ValidationError('Já existe uma conta com este e-mail.')
        return email

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        password_confirmation = cleaned_data.get('password_confirmation')
        if password or password_confirmation:
            if password != password_confirmation:
                self.add_error('password_confirmation', 'As senhas não coincidem.')
            elif password:
                try:
                    password_validation.validate_password(password, self.instance)
                except ValidationError as error:
                    self.add_error('password', error)
        return cleaned_data

    @transaction.atomic
    def save(self, commit=True):
        administrator = super().save(commit=False)
        administrator.email = self.cleaned_data['email']
        administrator.is_staff = True
        password = self.cleaned_data.get('password')
        if password:
            administrator.set_password(password)
        if commit:
            administrator.save()
        return administrator


class QuoteRequestForm(forms.ModelForm):
    products = forms.ModelMultipleChoiceField(
        label='Produtos de interesse',
        queryset=Product.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
    )
    services = forms.ModelMultipleChoiceField(
        label='Serviços de interesse',
        queryset=Service.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
    )

    class Meta:
        model = QuoteRequest
        fields = ('products', 'services', 'details')
        widgets = {
            'details': forms.Textarea(
                attrs={
                    'rows': 5,
                    'placeholder': 'Conte o que você precisa, informe medidas aproximadas ou tire suas dúvidas.',
                },
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['products'].queryset = Product.objects.select_related('category').filter(
            show_in_showcase=True
        )
        self.fields['services'].queryset = Service.objects.filter(show_in_showcase=True)


class ProductManagementForm(forms.ModelForm):
    category = forms.ModelChoiceField(
        label='Categoria existente',
        queryset=Category.objects.all(),
        required=False,
        empty_label='Selecione uma categoria',
    )
    new_category = forms.CharField(
        label='Ou crie uma categoria',
        max_length=100,
        required=False,
        help_text='Preencha somente se a categoria ainda não existir.',
    )

    class Meta:
        model = Product
        fields = (
            'name',
            'category',
            'new_category',
            'price',
            'stock_quantity',
            'show_in_showcase',
            'description',
            'photo',
        )
        widgets = {'description': forms.Textarea(attrs={'rows': 4})}

    def clean(self):
        cleaned_data = super().clean()
        if not cleaned_data.get('category') and not cleaned_data.get('new_category', '').strip():
            self.add_error('category', 'Selecione ou crie uma categoria.')
        return cleaned_data

    @transaction.atomic
    def save(self, commit=True):
        instance = super().save(commit=False)
        new_category = self.cleaned_data.get('new_category', '').strip()
        if new_category:
            category = Category.objects.filter(name__iexact=new_category).first()
            instance.category = category or Category.objects.create(name=new_category)
        else:
            instance.category = self.cleaned_data['category']
        if commit:
            instance.save()
            self.save_m2m()
        return instance


class ProductStockChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, product):
        return f'{product.name} — {product.stock_quantity} em estoque'


class ProductStockExitForm(forms.Form):
    product = ProductStockChoiceField(
        label='Produto',
        queryset=Product.objects.none(),
        empty_label='Selecione um produto',
    )
    quantity = forms.IntegerField(
        label='Quantidade da saída',
        min_value=1,
        widget=forms.NumberInput(
            attrs={
                'min': 1,
                'step': 1,
                'inputmode': 'numeric',
                'placeholder': 'Ex.: 2',
            }
        ),
    )
    notes = forms.CharField(
        label='Observação',
        max_length=240,
        required=False,
        widget=forms.TextInput(
            attrs={
                'placeholder': 'Ex.: retirada para instalação do orçamento 152',
                'autocomplete': 'off',
            }
        ),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['product'].queryset = Product.objects.select_related('category').all()

    def clean(self):
        cleaned_data = super().clean()
        product = cleaned_data.get('product')
        quantity = cleaned_data.get('quantity')
        if product and quantity and quantity > product.stock_quantity:
            self.add_error(
                'quantity',
                f'Estoque insuficiente. Há {product.stock_quantity} unidade(s) disponível(is).',
            )
        return cleaned_data


class CategoryManagementForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ('name',)
        labels = {'name': 'Nome da categoria'}
        widgets = {
            'name': forms.TextInput(
                attrs={
                    'placeholder': 'Ex.: Espelhos',
                    'autocomplete': 'off',
                }
            ),
        }

    def clean_name(self):
        name = self.cleaned_data['name'].strip()
        if Category.objects.filter(name__iexact=name).exists():
            raise ValidationError('Já existe uma categoria com este nome.')
        return name


class ServiceManagementForm(forms.ModelForm):
    class Meta:
        model = Service
        fields = ('name', 'service_type', 'show_in_showcase', 'description', 'photo')
        widgets = {'description': forms.Textarea(attrs={'rows': 4})}


class CashTransactionForm(forms.ModelForm):
    transaction_date = forms.DateField(
        label='Data do lançamento',
        input_formats=('%Y-%m-%d',),
        widget=forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}),
    )
    amount = BrazilianDecimalField(
        label='Valor',
        min_value=Decimal('0.01'),
        max_digits=12,
        decimal_places=2,
        widget=forms.TextInput(
            attrs={
                'inputmode': 'decimal',
                'placeholder': '0,00',
                'autocomplete': 'off',
            }
        ),
    )

    class Meta:
        model = CashTransaction
        fields = (
            'transaction_date',
            'kind',
            'description',
            'amount',
            'payment_method',
            'notes',
        )
        widgets = {
            'description': forms.TextInput(
                attrs={'placeholder': 'Ex.: Pagamento do orçamento 152', 'autocomplete': 'off'}
            ),
            'notes': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Informações adicionais'}),
        }


class EmployeeForm(forms.ModelForm):
    cpf = forms.CharField(
        label='CPF',
        max_length=14,
        widget=forms.TextInput(
            attrs={
                'inputmode': 'numeric',
                'placeholder': '000.000.000-00',
                'autocomplete': 'off',
            }
        ),
    )
    monthly_salary = BrazilianDecimalField(
        label='Salário mensal',
        min_value=0,
        max_digits=12,
        decimal_places=2,
        widget=forms.TextInput(
            attrs={
                'inputmode': 'decimal',
                'placeholder': '0,00',
                'autocomplete': 'off',
            }
        ),
    )

    class Meta:
        model = Employee
        fields = ('photo', 'full_name', 'cpf', 'monthly_salary')
        widgets = {
            'full_name': forms.TextInput(attrs={'autocomplete': 'name'}),
        }

    def clean_cpf(self):
        cpf = only_digits(self.cleaned_data['cpf'])
        validate_cpf(cpf)
        duplicate = Employee.objects.filter(cpf_hash=blind_index(cpf, 'employee.cpf'))
        if self.instance.pk:
            duplicate = duplicate.exclude(pk=self.instance.pk)
        if duplicate.exists():
            raise ValidationError('Já existe um funcionário com este CPF.')
        return cpf


class SupplierForm(forms.ModelForm):
    tax_id = forms.CharField(
        label='CPF ou CNPJ',
        max_length=18,
        required=False,
        widget=forms.TextInput(
            attrs={'inputmode': 'numeric', 'placeholder': 'Somente números ou com pontuação'}
        ),
    )

    class Meta:
        model = Supplier
        fields = (
            'name',
            'contact_name',
            'tax_id',
            'phone',
            'email',
            'address',
            'is_active',
            'notes',
        )
        widgets = {
            'phone': forms.TextInput(attrs={'inputmode': 'tel', 'autocomplete': 'tel'}),
            'email': forms.EmailInput(attrs={'autocomplete': 'email'}),
            'address': forms.TextInput(attrs={'autocomplete': 'street-address'}),
            'notes': forms.Textarea(attrs={'rows': 3}),
        }

    def clean_tax_id(self):
        tax_id = only_digits(self.cleaned_data.get('tax_id', ''))
        if tax_id:
            if len(tax_id) == 11:
                validate_cpf(tax_id)
            elif len(tax_id) == 14:
                validate_cnpj(tax_id)
            else:
                raise ValidationError('Informe um CPF com 11 dígitos ou CNPJ com 14 dígitos.')
            duplicate = Supplier.objects.filter(
                tax_id_hash=blind_index(tax_id, 'supplier.tax_id')
            )
            if self.instance.pk:
                duplicate = duplicate.exclude(pk=self.instance.pk)
            if duplicate.exists():
                raise ValidationError('Já existe um fornecedor com este CPF ou CNPJ.')
        return tax_id


class ExpenseForm(forms.ModelForm):
    expense_date = forms.DateField(
        label='Data do gasto',
        input_formats=('%Y-%m-%d',),
        widget=forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}),
    )
    amount = BrazilianDecimalField(
        label='Valor',
        min_value=Decimal('0.01'),
        max_digits=12,
        decimal_places=2,
        widget=forms.TextInput(
            attrs={'inputmode': 'decimal', 'placeholder': '0,00', 'autocomplete': 'off'}
        ),
    )

    class Meta:
        model = Expense
        fields = (
            'expense_date',
            'category',
            'description',
            'amount',
            'payment_method',
            'supplier',
            'notes',
        )
        widgets = {
            'description': forms.TextInput(
                attrs={'placeholder': 'Ex.: Conta de energia da oficina', 'autocomplete': 'off'}
            ),
            'notes': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Informações adicionais'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        supplier_filter = Q(is_active=True)
        if self.instance and self.instance.supplier_id:
            supplier_filter |= Q(pk=self.instance.supplier_id)
        self.fields['supplier'].queryset = Supplier.objects.filter(supplier_filter)


class PayrollForm(forms.ModelForm):
    competence = forms.DateField(
        label='Competência',
        input_formats=('%Y-%m',),
        widget=forms.DateInput(format='%Y-%m', attrs={'type': 'month'}),
    )
    gross_salary = BrazilianDecimalField(
        label='Salário-base',
        min_value=0,
        max_digits=12,
        decimal_places=2,
        widget=forms.TextInput(attrs={'inputmode': 'decimal', 'placeholder': '0,00'}),
    )
    additions = BrazilianDecimalField(
        label='Acréscimos',
        min_value=0,
        max_digits=12,
        decimal_places=2,
        initial=Decimal('0.00'),
        widget=forms.TextInput(attrs={'inputmode': 'decimal', 'placeholder': '0,00'}),
    )
    deductions = BrazilianDecimalField(
        label='Descontos',
        min_value=0,
        max_digits=12,
        decimal_places=2,
        initial=Decimal('0.00'),
        widget=forms.TextInput(attrs={'inputmode': 'decimal', 'placeholder': '0,00'}),
    )
    payment_date = forms.DateField(
        label='Data do pagamento',
        input_formats=('%Y-%m-%d',),
        widget=forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}),
    )

    class Meta:
        model = Payroll
        fields = (
            'employee',
            'competence',
            'gross_salary',
            'additions',
            'deductions',
            'payment_date',
            'payment_method',
            'notes',
        )
        widgets = {'notes': forms.Textarea(attrs={'rows': 3})}

    def clean(self):
        cleaned_data = super().clean()
        competence = cleaned_data.get('competence')
        if competence:
            cleaned_data['competence'] = competence.replace(day=1)
        gross_salary = cleaned_data.get('gross_salary') or Decimal('0.00')
        additions = cleaned_data.get('additions') or Decimal('0.00')
        deductions = cleaned_data.get('deductions') or Decimal('0.00')
        if gross_salary + additions - deductions <= 0:
            self.add_error('deductions', 'O valor líquido da folha deve ser maior que zero.')
        return cleaned_data


class SystemSettingsForm(forms.ModelForm):
    tax_id = forms.CharField(
        label='CNPJ',
        max_length=18,
        required=False,
        widget=forms.TextInput(attrs={'inputmode': 'numeric'}),
    )

    class Meta:
        model = SystemSettings
        fields = ('company_name', 'tax_id', 'phone', 'email', 'address', 'financial_manager')
        widgets = {
            'phone': forms.TextInput(attrs={'inputmode': 'tel'}),
            'email': forms.EmailInput(attrs={'autocomplete': 'email'}),
            'address': forms.TextInput(attrs={'autocomplete': 'street-address'}),
        }

    def clean_tax_id(self):
        tax_id = only_digits(self.cleaned_data.get('tax_id', ''))
        if tax_id:
            validate_cnpj(tax_id)
        return tax_id


class CustomerManagementForm(forms.ModelForm):
    is_active = forms.BooleanField(label='Conta ativa', required=False)

    class Meta:
        model = Profile
        fields = (
            'account_type',
            'document',
            'email',
            'full_name',
            'corporate_name',
            'street',
            'neighborhood',
            'house_number',
            'reference_point',
            'phone',
            'profile_photo',
            'is_active',
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['is_active'].initial = self.instance.user.is_active

    def clean_document(self):
        document = only_digits(self.cleaned_data['document'])
        account_type = self.data.get('account_type')
        if account_type == Profile.AccountType.INDIVIDUAL:
            validate_cpf(document)
        elif account_type == Profile.AccountType.COMPANY:
            validate_cnpj(document)
        if Profile.objects.filter(
            document_hash=blind_index(document, 'profile.document')
        ).exclude(pk=self.instance.pk).exists():
            raise ValidationError('Já existe uma conta com este CPF ou CNPJ.')
        return document

    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()
        if Profile.objects.filter(
            email_hash=blind_index(email, 'profile.email')
        ).exclude(pk=self.instance.pk).exists():
            raise ValidationError('Já existe uma conta com este e-mail.')
        return email

    def clean_phone(self):
        phone = only_digits(self.cleaned_data.get('phone', ''))
        if phone and len(phone) != 11:
            raise ValidationError('Informe um telefone com DDD e 11 dígitos.')
        return phone

    @transaction.atomic
    def save(self, commit=True):
        profile = super().save(commit=False)
        if commit:
            profile.save()
            self.save_m2m()
            user = profile.user
            user.username = f'acct_{uuid.uuid4().hex}'
            user.email = ''
            user.is_active = self.cleaned_data['is_active']
            user.save(update_fields=('username', 'email', 'is_active'))
        return profile
