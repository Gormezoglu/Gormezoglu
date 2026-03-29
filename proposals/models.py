from django.db import models
from django.contrib.auth.models import User


class ProposalType(models.TextChoices):
    SERVIS_SOZLESMESI = 'servis_sozlesmesi', 'Servis Sözleşmesi'
    IHALE             = 'ihale',             'İhale'
    HIZMET_ALIMI      = 'hizmet_alimi',      'Hizmet Alımı'
    SATIN_ALMA        = 'satin_alma',        'Satın Alma'
    DIGER             = 'diger',             'Diğer'


class ProposalStatus(models.TextChoices):
    DRAFT    = 'draft',    'Taslak'
    SENT     = 'sent',     'Gönderildi'
    ACCEPTED = 'accepted', 'Kabul Edildi'
    REJECTED = 'rejected', 'Reddedildi'


# Proposal types that route to a Tender on acceptance; all others → Contract
TENDER_PROPOSAL_TYPES = {ProposalType.IHALE}


class Proposal(models.Model):
    title           = models.CharField(max_length=255)
    description     = models.TextField(blank=True)
    proposal_type   = models.CharField(max_length=30, choices=ProposalType.choices, default=ProposalType.SERVIS_SOZLESMESI)
    status          = models.CharField(max_length=20, choices=ProposalStatus.choices, default=ProposalStatus.DRAFT)
    party           = models.ForeignKey('parties.Party', on_delete=models.PROTECT, related_name='proposals')
    value           = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    currency        = models.CharField(max_length=3, default='TRY')
    document        = models.FileField(upload_to='proposals/documents/', null=True, blank=True)
    current_version = models.PositiveIntegerField(default=1)
    created_by      = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_proposals')
    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} (v{self.current_version})"

    @property
    def routes_to_tender(self):
        return self.proposal_type in TENDER_PROPOSAL_TYPES

    @property
    def is_editable(self):
        return self.status in (ProposalStatus.DRAFT, ProposalStatus.SENT)

    @property
    def promoted_object(self):
        """Return the Contract or Tender this proposal was promoted to, or None."""
        if hasattr(self, 'contract'):
            return ('contract', self.contract)
        if hasattr(self, 'tender'):
            return ('tender', self.tender)
        return None


class ProposalRevision(models.Model):
    """Snapshot of a Proposal's state before each edit."""
    proposal        = models.ForeignKey(Proposal, on_delete=models.CASCADE, related_name='revisions')
    version_number  = models.PositiveIntegerField()
    title           = models.CharField(max_length=255)
    description     = models.TextField(blank=True)
    proposal_type   = models.CharField(max_length=30, choices=ProposalType.choices)
    party           = models.ForeignKey('parties.Party', on_delete=models.SET_NULL, null=True)
    value           = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    currency        = models.CharField(max_length=3, default='TRY')
    revision_note   = models.TextField(blank=True, help_text='What changed in this revision?')
    created_by      = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at      = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-version_number']

    def __str__(self):
        return f"{self.proposal.title} — v{self.version_number}"
