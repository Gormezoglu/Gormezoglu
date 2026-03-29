from django import forms
from .models import Tender


class TenderForm(forms.ModelForm):
    class Meta:
        model = Tender
        fields = ['title', 'description', 'party', 'status', 'deadline', 'value', 'currency', 'awarded_to', 'notes']
        widgets = {
            'title':      forms.TextInput(attrs={'class': 'form-control'}),
            'description':forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'party':      forms.Select(attrs={'class': 'form-select'}),
            'status':     forms.Select(attrs={'class': 'form-select'}),
            'deadline':   forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'value':      forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'currency':   forms.TextInput(attrs={'class': 'form-control', 'maxlength': '3'}),
            'awarded_to': forms.TextInput(attrs={'class': 'form-control'}),
            'notes':      forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }
