from django.db import models
from django.contrib.auth.models import User


class TenderStatus(models.TextChoices):
    OPEN        = 'open',        'Açık'
    EVALUATION  = 'evaluation',  'Değerlendirmede'
    AWARDED     = 'awarded',     'Kazanan Belirlendi'
    CANCELLED   = 'cancelled',   'İptal Edildi'


class Tender(models.Model):
    title            = models.CharField(max_length=255)
    description      = models.TextField(blank=True)
    party            = models.ForeignKey('parties.Party', on_delete=models.PROTECT, related_name='tenders')
    status           = models.CharField(max_length=20, choices=TenderStatus.choices, default=TenderStatus.OPEN)
    deadline         = models.DateField(null=True, blank=True)
    value            = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    currency         = models.CharField(max_length=3, default='TRY')
    awarded_to       = models.CharField(max_length=255, blank=True, help_text='Name of the awarded bidder')
    notes            = models.TextField(blank=True)
    source_proposal  = models.OneToOneField(
        'proposals.Proposal',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='tender',
    )
    created_by       = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_tenders')
    created_at       = models.DateTimeField(auto_now_add=True)
    updated_at       = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title

    @property
    def is_overdue(self):
        from django.utils import timezone
        if self.deadline and self.status == TenderStatus.OPEN:
            return self.deadline < timezone.now().date()
        return False
