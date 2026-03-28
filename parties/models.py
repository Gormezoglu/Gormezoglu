from django.db import models


class PartyType(models.TextChoices):
    VENDOR = 'vendor', 'Vendor'
    CUSTOMER = 'customer', 'Customer'
    PARTNER = 'partner', 'Partner'
    EMPLOYEE = 'employee', 'Employee'
    OTHER = 'other', 'Other'


class Party(models.Model):
    name = models.CharField(max_length=255)
    party_type = models.CharField(max_length=20, choices=PartyType.choices, default=PartyType.VENDOR)
    contact_name = models.CharField(max_length=255, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=50, blank=True)
    address = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = 'parties'
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.get_party_type_display()})"

    @property
    def active_contract_count(self):
        return self.contracts.filter(status='active').count()

    @property
    def total_contract_count(self):
        return self.contracts.count()
