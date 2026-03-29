from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.urls import reverse_lazy
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView, TemplateView
from django.utils import timezone
from django.db.models import Count, Sum, Q
from .models import Contract, ContractStatus
from .forms import ContractForm, ContractFilterForm


class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'dashboard.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        today = timezone.now().date()
        from django.conf import settings
        threshold = getattr(settings, 'EXPIRY_NOTIFICATION_DAYS', 30)
        threshold_date = today + timezone.timedelta(days=threshold)

        ctx['total_contracts'] = Contract.objects.count()
        ctx['active_contracts'] = Contract.objects.filter(status=ContractStatus.ACTIVE).count()
        ctx['expired_contracts'] = Contract.objects.filter(status=ContractStatus.EXPIRED).count()
        ctx['draft_contracts'] = Contract.objects.filter(status=ContractStatus.DRAFT).count()
        ctx['expiring_soon'] = Contract.objects.filter(
            status=ContractStatus.ACTIVE,
            end_date__lte=threshold_date,
            end_date__gte=today,
        ).count()
        ctx['total_value'] = Contract.objects.filter(
            status=ContractStatus.ACTIVE
        ).aggregate(total=Sum('value'))['total'] or 0
        from proposals.models import Proposal, ProposalStatus as PS
        ctx['draft_proposals']    = Proposal.objects.filter(status=PS.DRAFT).count()
        ctx['sent_proposals']     = Proposal.objects.filter(status=PS.SENT).count()
        ctx['accepted_proposals'] = Proposal.objects.filter(status=PS.ACCEPTED).count()
        ctx['rejected_proposals'] = Proposal.objects.filter(status=PS.REJECTED).count()
        ctx['recent_contracts'] = Contract.objects.select_related('party').order_by('-created_at')[:5]
        ctx['expiring_contracts'] = Contract.objects.filter(
            status=ContractStatus.ACTIVE,
            end_date__lte=threshold_date,
            end_date__gte=today,
        ).select_related('party').order_by('end_date')[:5]
        return ctx


class ContractListView(LoginRequiredMixin, ListView):
    model = Contract
    template_name = 'contracts/contract_list.html'
    context_object_name = 'contracts'
    paginate_by = 20

    def get_queryset(self):
        qs = Contract.objects.select_related('party', 'created_by')
        status = self.request.GET.get('status')
        contract_type = self.request.GET.get('contract_type')
        search = self.request.GET.get('q')
        if status:
            qs = qs.filter(status=status)
        if contract_type:
            qs = qs.filter(contract_type=contract_type)
        if search:
            qs = qs.filter(Q(title__icontains=search) | Q(party__name__icontains=search))
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['filter_form'] = ContractFilterForm(self.request.GET)
        return ctx


class ContractDetailView(LoginRequiredMixin, DetailView):
    model = Contract
    template_name = 'contracts/contract_detail.html'
    context_object_name = 'contract'


class ContractCreateView(LoginRequiredMixin, CreateView):
    model = Contract
    form_class = ContractForm
    template_name = 'contracts/contract_form.html'
    success_url = reverse_lazy('contract-list')

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['action'] = 'Add'
        return ctx


class ContractUpdateView(LoginRequiredMixin, UpdateView):
    model = Contract
    form_class = ContractForm
    template_name = 'contracts/contract_form.html'
    success_url = reverse_lazy('contract-list')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['action'] = 'Edit'
        return ctx


class ContractDeleteView(LoginRequiredMixin, DeleteView):
    model = Contract
    template_name = 'contracts/contract_confirm_delete.html'
    success_url = reverse_lazy('contract-list')
