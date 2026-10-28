from decimal import Decimal

from django import forms
from django.core.exceptions import ValidationError
from accounts.models import Profile, only_digits, validate_cnpj, validate_cpf
from calculator.models import Material
from glazing_services.models import Service
from products.models import Product

from .models import Sale, SaleItem, money


class BrazilianDecimalField(forms.DecimalField):
    def to_python(self, value):
        if isinstance(value, str) and ',' in value:
            value = value.strip().replace('.', '').replace(',', '.')
        return super().to_python(value)


class CustomerChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, profile):
        name = profile.full_name or profile.corporate_name or profile.email
        return f'{name} — {profile.formatted_document}'


class SaleForm(forms.ModelForm):
    customer = CustomerChoiceField(
        label='Cliente cadastrado', queryset=Profile.objects.none(), required=False,
        empty_label='Selecione um cliente',
    )
    customer_name = forms.CharField(label='Nome do cliente de balcão', max_length=180, required=False)
    customer_document = forms.CharField(
        label='CPF ou CNPJ', max_length=18, required=False,
        widget=forms.TextInput(attrs={'inputmode': 'numeric', 'autocomplete': 'off'}),
    )
    customer_contact = forms.CharField(
        label='Contato', max_length=120, required=False,
        widget=forms.TextInput(attrs={'placeholder': 'Telefone, WhatsApp ou e-mail'}),
    )
    discount = BrazilianDecimalField(
        label='Desconto geral', min_value=0, max_digits=12, decimal_places=2,
        widget=forms.TextInput(attrs={'inputmode': 'decimal', 'placeholder': '0,00'}),
    )
    amount_paid = BrazilianDecimalField(
        label='Total pago', min_value=0, max_digits=12, decimal_places=2,
        widget=forms.TextInput(attrs={'inputmode': 'decimal', 'placeholder': '0,00'}),
    )

    class Meta:
        model = Sale
        fields = (
            'customer_type', 'customer', 'customer_name', 'customer_document',
            'customer_contact', 'discount', 'payment_method', 'amount_paid', 'notes',
        )
        widgets = {'notes': forms.Textarea(attrs={'rows': 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['customer'].queryset = Profile.objects.select_related('user').filter(
            user__is_active=True
        )
        self.fields['payment_method'].required = False
        self.fields['discount'].initial = self.instance.discount or Decimal('0.00')
        self.fields['amount_paid'].initial = self.instance.amount_paid or Decimal('0.00')

    def clean_customer_document(self):
        document = only_digits(self.cleaned_data.get('customer_document', ''))
        if document:
            if len(document) == 11:
                validate_cpf(document)
            elif len(document) == 14:
                validate_cnpj(document)
            else:
                raise ValidationError('Informe um CPF com 11 dígitos ou CNPJ com 14 dígitos.')
        return document

    def clean(self):
        cleaned_data = super().clean()
        customer_type = cleaned_data.get('customer_type')
        if customer_type == Sale.CustomerType.REGISTERED and not cleaned_data.get('customer'):
            self.add_error('customer', 'Selecione um cliente cadastrado.')
        elif customer_type == Sale.CustomerType.WALK_IN_IDENTIFIED:
            if not (cleaned_data.get('customer_name') or '').strip():
                self.add_error('customer_name', 'Informe o nome do cliente de balcão.')
        discount = cleaned_data.get('discount')
        subtotal = (
            sum((item.total for item in self.instance.items.all()), Decimal('0.00'))
            if self.instance.pk
            else Decimal('0.00')
        )
        if discount is not None and discount > subtotal:
            self.add_error('discount', 'O desconto da venda não pode superar o subtotal atual.')
        return cleaned_data

    def save(self, commit=True, employee=None):
        sale = super().save(commit=False)
        if sale.customer_type == Sale.CustomerType.REGISTERED:
            sale.copy_registered_customer()
        elif sale.customer_type == Sale.CustomerType.WALK_IN_IDENTIFIED:
            sale.customer = None
            sale.customer_name = self.cleaned_data['customer_name'].strip()
            sale.customer_document = self.cleaned_data.get('customer_document', '')
            sale.customer_contact = self.cleaned_data.get('customer_contact', '').strip()
            sale.customer_email = ''
            sale.customer_address = ''
        else:
            sale.customer = None
            sale.customer_name = 'Cliente Balcão'
            sale.customer_document = ''
            sale.customer_contact = ''
            sale.customer_email = ''
            sale.customer_address = ''
        if sale.employee_id is None:
            sale.employee = employee
        sale.full_clean()
        if commit:
            sale.save()
            if sale.pk:
                sale.recalculate_totals(save=True)
        return sale


class ItemDiscountMixin:
    discount = BrazilianDecimalField(
        label='Desconto do item', min_value=0, max_digits=12, decimal_places=2,
        initial=Decimal('0.00'),
        widget=forms.TextInput(attrs={'inputmode': 'decimal', 'placeholder': '0,00'}),
    )


class ProductItemForm(ItemDiscountMixin, forms.Form):
    product = forms.ModelChoiceField(
        label='Produto', queryset=Product.objects.none(), empty_label='Selecione um produto'
    )
    quantity = forms.IntegerField(
        label='Quantidade (unidades)', min_value=1,
        widget=forms.NumberInput(attrs={'min': 1, 'step': 1, 'inputmode': 'numeric'}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['product'].queryset = Product.objects.select_related('category').all()

    def save(self, sale):
        product = self.cleaned_data['product']
        return SaleItem.objects.create(
            sale=sale,
            item_type=SaleItem.ItemType.PRODUCT,
            product=product,
            description=product.name,
            unit=SaleItem.Unit.UNIT,
            quantity=Decimal(self.cleaned_data['quantity']),
            unit_price=product.price,
            discount=self.cleaned_data['discount'],
        )


class MaterialItemForm(ItemDiscountMixin, forms.Form):
    material = forms.ModelChoiceField(
        label='Vidro ou material', queryset=Material.objects.none(),
        empty_label='Selecione um material por m²',
    )
    width_mm = BrazilianDecimalField(
        label='Largura (mm)', min_value=Decimal('0.01'), max_digits=10, decimal_places=2,
        widget=forms.NumberInput(attrs={'min': '0.01', 'step': '0.01', 'inputmode': 'decimal'}),
    )
    height_mm = BrazilianDecimalField(
        label='Altura (mm)', min_value=Decimal('0.01'), max_digits=10, decimal_places=2,
        widget=forms.NumberInput(attrs={'min': '0.01', 'step': '0.01', 'inputmode': 'decimal'}),
    )
    piece_count = forms.IntegerField(
        label='Quantidade de peças', min_value=1,
        widget=forms.NumberInput(attrs={'min': 1, 'step': 1, 'inputmode': 'numeric'}),
    )
    unit_price = BrazilianDecimalField(
        label='Preço por m²', min_value=0, max_digits=12, decimal_places=2,
        widget=forms.TextInput(attrs={'inputmode': 'decimal', 'placeholder': '0,00'}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['material'].queryset = Material.objects.filter(
            unit_type=Material.UnitType.SQUARE_METER
        )

    def save(self, sale):
        material = self.cleaned_data['material']
        return SaleItem.objects.create(
            sale=sale,
            item_type=SaleItem.ItemType.MATERIAL,
            material=material,
            description=material.name,
            unit=SaleItem.Unit.SQUARE_METER,
            quantity=Decimal('1'),
            width_mm=self.cleaned_data['width_mm'],
            height_mm=self.cleaned_data['height_mm'],
            piece_count=self.cleaned_data['piece_count'],
            unit_price=self.cleaned_data['unit_price'],
            discount=self.cleaned_data['discount'],
        )


class ServiceItemForm(ItemDiscountMixin, forms.Form):
    service = forms.ModelChoiceField(
        label='Serviço', queryset=Service.objects.none(), empty_label='Selecione um serviço'
    )
    quantity = BrazilianDecimalField(
        label='Quantidade', min_value=Decimal('0.000001'), max_digits=14, decimal_places=6,
        initial=Decimal('1'),
        widget=forms.NumberInput(attrs={'min': '0.000001', 'step': '0.000001'}),
    )
    unit_price = BrazilianDecimalField(
        label='Preço unitário', min_value=0, max_digits=12, decimal_places=2,
        widget=forms.TextInput(attrs={'inputmode': 'decimal', 'placeholder': '0,00'}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['service'].queryset = Service.objects.all()

    def save(self, sale):
        service = self.cleaned_data['service']
        return SaleItem.objects.create(
            sale=sale,
            item_type=SaleItem.ItemType.SERVICE,
            service=service,
            description=service.name,
            unit=SaleItem.Unit.SERVICE,
            quantity=self.cleaned_data['quantity'],
            unit_price=self.cleaned_data['unit_price'],
            discount=self.cleaned_data['discount'],
        )


class CancellationForm(forms.Form):
    reason = forms.CharField(
        label='Motivo do cancelamento', min_length=3,
        widget=forms.Textarea(attrs={'rows': 4, 'placeholder': 'Descreva o motivo do estorno.'}),
    )
