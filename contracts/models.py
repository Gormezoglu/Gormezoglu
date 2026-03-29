from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class ContractStatus(models.TextChoices):
    DRAFT      = 'draft',      'Draft'
    ACTIVE     = 'active',     'Active'
    EXPIRED    = 'expired',    'Expired'
    TERMINATED = 'terminated', 'Terminated'


class ContractType(models.TextChoices):
    SERVICE       = 'service',       'Service Agreement'
    PURCHASE      = 'purchase',      'Purchase Agreement'
    EMPLOYMENT    = 'employment',    'Employment Contract'
    NDA           = 'nda',           'Non-Disclosure Agreement'
    LEASE         = 'lease',         'Lease Agreement'
    BAKIM_ONARIM  = 'bakim_onarim',  'Bakım Onarım'
    OTHER         = 'other',         'Other'


class PaymentStatus(models.TextChoices):
    PENDING   = 'pending',   'Bekliyor'
    PAID      = 'paid',      'Ödendi'
    OVERDUE   = 'overdue',   'Gecikmiş'
    CANCELLED = 'cancelled', 'İptal'


def _add_months(d, months):
    """Add months to a date without external dependencies."""
    month = d.month - 1 + months
    year  = d.year + month // 12
    month = month % 12 + 1
    import calendar
    day = min(d.day, calendar.monthrange(year, month)[1])
    return d.replace(year=year, month=month, day=day)


class Contract(models.Model):
    title           = models.CharField(max_length=255)
    description     = models.TextField(blank=True)
    contract_type   = models.CharField(max_length=20, choices=ContractType.choices, default=ContractType.SERVICE)
    status          = models.CharField(max_length=20, choices=ContractStatus.choices, default=ContractStatus.DRAFT)
    party           = models.ForeignKey('parties.Party', on_delete=models.PROTECT, related_name='contracts')
    start_date      = models.DateField()
    end_date        = models.DateField(null=True, blank=True)
    value           = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    currency        = models.CharField(max_length=3, default='USD')
    monthly_payment = models.DecimalField(
        max_digits=15, decimal_places=2, null=True, blank=True,
        help_text='Monthly payment amount for Bakım Onarım contracts.',
    )
    document        = models.FileField(upload_to='contracts/documents/', null=True, blank=True)
    created_by      = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_contracts')
    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)
    expiry_notification_sent = models.BooleanField(default=False)
    source_proposal = models.OneToOneField(
        'proposals.Proposal',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='contract',
    )

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title

    @property
    def is_bakim_onarim(self):
        return self.contract_type == ContractType.BAKIM_ONARIM

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

    def generate_payment_schedule(self):
        """
        Create ContractPayment records for every month between start_date
        and end_date. Existing paid/cancelled records are left untouched;
        pending ones are recreated to reflect date/amount changes.
        Requires contract_type == BAKIM_ONARIM and monthly_payment set.
        """
        if not self.is_bakim_onarim or not self.monthly_payment or not self.start_date:
            return 0

        end = self.end_date or _add_months(self.start_date, 11)

        # Delete only pending/overdue payments so paid ones are preserved
        self.payments.filter(status__in=[PaymentStatus.PENDING, PaymentStatus.OVERDUE]).delete()

        created = 0
        current = self.start_date
        while current <= end:
            period = current.strftime('%Y-%m')
            # Skip months that are already paid or cancelled
            if not self.payments.filter(period_label=period).exists():
                ContractPayment.objects.create(
                    contract=self,
                    period_label=period,
                    due_date=current,
                    amount=self.monthly_payment,
                    currency=self.currency,
                )
                created += 1
            current = _add_months(current, 1)
        return created


class ContractPayment(models.Model):
    contract     = models.ForeignKey(Contract, on_delete=models.CASCADE, related_name='payments')
    period_label = models.CharField(max_length=7, help_text='YYYY-MM')
    due_date     = models.DateField()
    amount       = models.DecimalField(max_digits=15, decimal_places=2)
    currency     = models.CharField(max_length=3, default='TRY')
    status       = models.CharField(max_length=20, choices=PaymentStatus.choices, default=PaymentStatus.PENDING)
    paid_date    = models.DateField(null=True, blank=True)
    paid_by      = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='payments_made')
    notes        = models.TextField(blank=True)
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['due_date']
        unique_together = ['contract', 'period_label']

    def __str__(self):
        return f"{self.contract.title} — {self.period_label}"

    @property
    def is_overdue(self):
        return (
            self.status == PaymentStatus.PENDING
            and self.due_date < timezone.now().date()
        )
