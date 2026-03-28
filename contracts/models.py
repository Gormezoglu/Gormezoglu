from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class ContractStatus(models.TextChoices):
    DRAFT = 'draft', 'Draft'
    ACTIVE = 'active', 'Active'
    EXPIRED = 'expired', 'Expired'
    TERMINATED = 'terminated', 'Terminated'


class ContractType(models.TextChoices):
    SERVICE = 'service', 'Service Agreement'
    PURCHASE = 'purchase', 'Purchase Agreement'
    EMPLOYMENT = 'employment', 'Employment Contract'
    NDA = 'nda', 'Non-Disclosure Agreement'
    LEASE = 'lease', 'Lease Agreement'
    OTHER = 'other', 'Other'


class Contract(models.Model):
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    contract_type = models.CharField(max_length=20, choices=ContractType.choices, default=ContractType.SERVICE)
    status = models.CharField(max_length=20, choices=ContractStatus.choices, default=ContractStatus.DRAFT)
    party = models.ForeignKey('parties.Party', on_delete=models.PROTECT, related_name='contracts')
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    value = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    currency = models.CharField(max_length=3, default='USD')
    document = models.FileField(upload_to='contracts/documents/', null=True, blank=True)
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name='created_contracts'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    expiry_notification_sent = models.BooleanField(default=False)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title

    @property
    def is_expiring_soon(self):
        from django.conf import settings
        threshold = getattr(settings, 'EXPIRY_NOTIFICATION_DAYS', 30)
        if self.end_date and self.status == ContractStatus.ACTIVE:
            days = (self.end_date - timezone.now().date()).days
            return 0 <= days <= threshold
        return False

    @property
    def days_until_expiry(self):
        if self.end_date:
            return (self.end_date - timezone.now().date()).days
        return None

    @property
    def is_overdue(self):
        if self.end_date and self.status == ContractStatus.ACTIVE:
            return self.end_date < timezone.now().date()
        return False

    def update_expired_status(self):
        if self.end_date and self.status == ContractStatus.ACTIVE:
            if self.end_date < timezone.now().date():
                self.status = ContractStatus.EXPIRED
                self.save(update_fields=['status'])
