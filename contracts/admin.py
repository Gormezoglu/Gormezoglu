from django.contrib import admin
from .models import Contract


@admin.register(Contract)
class ContractAdmin(admin.ModelAdmin):
    list_display = ['title', 'contract_type', 'status', 'party', 'start_date', 'end_date', 'value', 'currency']
    list_filter = ['status', 'contract_type']
    search_fields = ['title', 'party__name']
    date_hierarchy = 'start_date'
    readonly_fields = ['created_at', 'updated_at', 'created_by']

    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
