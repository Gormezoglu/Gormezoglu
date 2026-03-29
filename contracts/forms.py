from django import forms
from .models import Contract


class ContractForm(forms.ModelForm):
    class Meta:
        model = Contract
        fields = [
            'title', 'description', 'contract_type', 'status',
            'party', 'start_date', 'end_date', 'value', 'monthly_payment', 'currency', 'document',
        ]
        widgets = {
            'title':           forms.TextInput(attrs={'class': 'form-control'}),
            'description':     forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'contract_type':   forms.Select(attrs={'class': 'form-select', 'id': 'id_contract_type'}),
            'status':          forms.Select(attrs={'class': 'form-select'}),
            'party':           forms.Select(attrs={'class': 'form-select'}),
            'start_date':      forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'end_date':        forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'value':           forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'monthly_payment': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'currency':        forms.TextInput(attrs={'class': 'form-control', 'maxlength': '3'}),
            'document':        forms.ClearableFileInput(attrs={'class': 'form-control'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        if start_date and end_date and end_date < start_date:
            raise forms.ValidationError('End date cannot be before start date.')
        return cleaned_data


class ContractFilterForm(forms.Form):
    STATUS_CHOICES = [('', 'All Statuses')] + list(Contract.status.field.choices)
    TYPE_CHOICES = [('', 'All Types')] + list(Contract.contract_type.field.choices)

    status = forms.ChoiceField(choices=STATUS_CHOICES, required=False,
                               widget=forms.Select(attrs={'class': 'form-select form-select-sm'}))
    contract_type = forms.ChoiceField(choices=TYPE_CHOICES, required=False,
                                      widget=forms.Select(attrs={'class': 'form-select form-select-sm'}))
    q = forms.CharField(required=False,
                        widget=forms.TextInput(attrs={'class': 'form-control form-control-sm',
                                                      'placeholder': 'Search contracts...'}))
