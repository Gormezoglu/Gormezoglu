from django import forms
from .models import Proposal


class ProposalForm(forms.ModelForm):
    revision_note = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 2,
                                     'placeholder': 'What changed? (shown in revision history)'}),
        help_text='Describe what changed in this revision.',
    )

    class Meta:
        model = Proposal
        fields = ['title', 'description', 'proposal_type', 'party', 'value', 'currency', 'document']
        widgets = {
            'title':         forms.TextInput(attrs={'class': 'form-control'}),
            'description':   forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'proposal_type': forms.Select(attrs={'class': 'form-select'}),
            'party':         forms.Select(attrs={'class': 'form-select'}),
            'value':         forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'currency':      forms.TextInput(attrs={'class': 'form-control', 'maxlength': '3'}),
            'document':      forms.ClearableFileInput(attrs={'class': 'form-control'}),
        }
