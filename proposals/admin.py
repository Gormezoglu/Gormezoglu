from django.contrib import admin
from .models import Proposal, ProposalRevision


class ProposalRevisionInline(admin.TabularInline):
    model = ProposalRevision
    extra = 0
    readonly_fields = ['version_number', 'title', 'proposal_type', 'value', 'currency', 'revision_note', 'created_by', 'created_at']
    can_delete = False


@admin.register(Proposal)
class ProposalAdmin(admin.ModelAdmin):
    list_display = ['title', 'proposal_type', 'status', 'party', 'current_version', 'value', 'currency', 'created_at']
    list_filter = ['status', 'proposal_type']
    search_fields = ['title', 'party__name']
    inlines = [ProposalRevisionInline]
    readonly_fields = ['current_version', 'created_at', 'updated_at']
