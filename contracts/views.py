from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy, reverse
from django.views import View
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView, TemplateView
from django.utils import timezone
from django.db.models import Sum, Q
from .models import Contract, ContractStatus, ContractPayment, PaymentStatus, ContractType
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

        # Overdue & upcoming Bakım Onarım payments
        ctx['overdue_payments'] = ContractPayment.objects.filter(
            status=PaymentStatus.PENDING,
            due_date__lt=today,
        ).select_related('contract', 'contract__party').order_by('due_date')[:5]
        ctx['upcoming_payments'] = ContractPayment.objects.filter(
            status=PaymentStatus.PENDING,
            due_date__gte=today,
            due_date__lte=today + timezone.timedelta(days=30),
        ).select_related('contract', 'contract__party').order_by('due_date')[:5]
        ctx['overdue_payment_count'] = ContractPayment.objects.filter(
            status=PaymentStatus.PENDING, due_date__lt=today,
        ).count()
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

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        if self.object.is_bakim_onarim:
            ctx['payments'] = self.object.payments.all()
            today = timezone.now().date()
            ctx['payment_stats'] = {
                'total':    self.object.payments.count(),
                'paid':     self.object.payments.filter(status=PaymentStatus.PAID).count(),
                'overdue':  self.object.payments.filter(status=PaymentStatus.PENDING, due_date__lt=today).count(),
                'pending':  self.object.payments.filter(status=PaymentStatus.PENDING, due_date__gte=today).count(),
            }
        return ctx


class ContractCreateView(LoginRequiredMixin, CreateView):
    model = Contract
    form_class = ContractForm
    template_name = 'contracts/contract_form.html'

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        response = super().form_valid(form)
        if self.object.is_bakim_onarim and self.object.monthly_payment:
            n = self.object.generate_payment_schedule()
            if n:
                messages.success(self.request, f'{n} monthly payment record(s) generated.')
        return response

    def get_success_url(self):
        return reverse('contract-detail', kwargs={'pk': self.object.pk})

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['action'] = 'Add'
        return ctx


class ContractUpdateView(LoginRequiredMixin, UpdateView):
    model = Contract
    form_class = ContractForm
    template_name = 'contracts/contract_form.html'

    def form_valid(self, form):
        response = super().form_valid(form)
        if self.object.is_bakim_onarim and self.object.monthly_payment:
            n = self.object.generate_payment_schedule()
            if n:
                messages.info(self.request, f'Payment schedule updated: {n} new record(s) created.')
        return response

    def get_success_url(self):
        return reverse('contract-detail', kwargs={'pk': self.object.pk})

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['action'] = 'Edit'
        return ctx


class ContractDeleteView(LoginRequiredMixin, DeleteView):
    model = Contract
    template_name = 'contracts/contract_confirm_delete.html'
    success_url = reverse_lazy('contract-list')


# ---------------------------------------------------------------------------
# Payment views
# ---------------------------------------------------------------------------

class PaymentMarkPaidView(LoginRequiredMixin, View):
    def post(self, request, pk):
        payment = get_object_or_404(ContractPayment, pk=pk)
        if payment.status == PaymentStatus.PENDING or payment.is_overdue:
            payment.status   = PaymentStatus.PAID
            payment.paid_date = timezone.now().date()
            payment.paid_by  = request.user
            payment.notes    = request.POST.get('notes', '')
            payment.save()
            messages.success(request, f'{payment.period_label} payment marked as paid.')
        else:
            messages.warning(request, 'Payment is already processed.')
        return redirect('contract-detail', pk=payment.contract_id)


class PaymentCancelView(LoginRequiredMixin, View):
    def post(self, request, pk):
        payment = get_object_or_404(ContractPayment, pk=pk)
        if payment.status in (PaymentStatus.PENDING, PaymentStatus.OVERDUE):
            payment.status = PaymentStatus.CANCELLED
            payment.save(update_fields=['status'])
            messages.warning(request, f'{payment.period_label} payment cancelled.')
        else:
            messages.error(request, 'Only pending payments can be cancelled.')
        return redirect('contract-detail', pk=payment.contract_id)


class PaymentOverviewView(LoginRequiredMixin, ListView):
    """Global overview of all Bakım Onarım payments."""
    template_name = 'contracts/payment_overview.html'
    context_object_name = 'payments'
    paginate_by = 30

    def get_queryset(self):
        today = timezone.now().date()
        qs = ContractPayment.objects.select_related('contract', 'contract__party', 'paid_by')
        tab = self.request.GET.get('tab', 'overdue')
        if tab == 'overdue':
            qs = qs.filter(status=PaymentStatus.PENDING, due_date__lt=today)
        elif tab == 'upcoming':
            qs = qs.filter(status=PaymentStatus.PENDING, due_date__gte=today)
        elif tab == 'paid':
            qs = qs.filter(status=PaymentStatus.PAID).order_by('-paid_date')
        else:
            pass  # all
        return qs.order_by('due_date')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        today = timezone.now().date()
        ctx['tab'] = self.request.GET.get('tab', 'overdue')
        ctx['overdue_count']  = ContractPayment.objects.filter(status=PaymentStatus.PENDING, due_date__lt=today).count()
        ctx['upcoming_count'] = ContractPayment.objects.filter(status=PaymentStatus.PENDING, due_date__gte=today).count()
        ctx['paid_count']     = ContractPayment.objects.filter(status=PaymentStatus.PAID).count()
        return ctx
