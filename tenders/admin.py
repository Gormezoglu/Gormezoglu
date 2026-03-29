from django.contrib import admin
from .models import Tender


@admin.register(Tender)
class TenderAdmin(admin.ModelAdmin):
    list_display = ['title', 'status', 'party', 'deadline', 'value', 'currency', 'awarded_to']
    list_filter = ['status']
    search_fields = ['title', 'party__name']
    readonly_fields = ['created_at', 'updated_at', 'source_proposal']
