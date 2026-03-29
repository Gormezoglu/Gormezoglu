from django.contrib import admin
from .models import Contract, ContractPayment


class ContractPaymentInline(admin.TabularInline):
    model = ContractPayment
    extra = 0
    fields = ['period_label', 'due_date', 'amount', 'currency', 'status', 'paid_date', 'paid_by']
    readonly_fields = ['period_label', 'due_date']


@admin.register(Contract)
class ContractAdmin(admin.ModelAdmin):
    list_display = ['title', 'contract_type', 'status', 'party', 'start_date', 'end_date', 'value', 'monthly_payment', 'currency']
    list_filter = ['status', 'contract_type']
    search_fields = ['title', 'party__name']
    date_hierarchy = 'start_date'
    readonly_fields = ['created_at', 'updated_at', 'created_by']
    inlines = [ContractPaymentInline]

    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(ContractPayment)
class ContractPaymentAdmin(admin.ModelAdmin):
    list_display = ['contract', 'period_label', 'due_date', 'amount', 'currency', 'status', 'paid_date']
    list_filter = ['status']
    search_fields = ['contract__title']
    date_hierarchy = 'due_date'
