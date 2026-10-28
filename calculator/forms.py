from django import forms

from .models import Material


class MaterialForm(forms.ModelForm):
    unit_price = forms.DecimalField(
        label='Valor por unidade',
        min_value=0,
        max_digits=12,
        decimal_places=2,
        localize=True,
        widget=forms.TextInput(
            attrs={
                'inputmode': 'decimal',
                'placeholder': '0,00',
                'autocomplete': 'off',
            }
        ),
        help_text='Use vírgula para os centavos. Exemplo: 150,00.',
    )

    class Meta:
        model = Material
        fields = ('name', 'unit_type', 'unit_price')
        labels = {
            'name': 'Nome do material',
            'unit_type': 'Como o material é cobrado',
        }
        widgets = {
            'name': forms.TextInput(
                attrs={
                    'placeholder': 'Ex.: Vidro temperado 8 mm',
                    'autocomplete': 'off',
                }
            ),
        }

    def clean_name(self):
        name = self.cleaned_data['name'].strip()
        duplicate = Material.objects.filter(name__iexact=name)
        if self.instance.pk:
            duplicate = duplicate.exclude(pk=self.instance.pk)
        if duplicate.exists():
            raise forms.ValidationError('Já existe um material com este nome.')
        return name
