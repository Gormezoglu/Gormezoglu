from django.contrib import admin
from .models import Party


@admin.register(Party)
class PartyAdmin(admin.ModelAdmin):
    list_display = ['name', 'party_type', 'contact_name', 'email', 'phone', 'total_contract_count']
    list_filter = ['party_type']
    search_fields = ['name', 'contact_name', 'email']
