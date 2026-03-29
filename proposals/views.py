from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy, reverse
from django.views import View
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView

from .models import Proposal, ProposalRevision, ProposalStatus, ProposalType
from .forms import ProposalForm


class ProposalListView(LoginRequiredMixin, ListView):
    model = Proposal
    template_name = 'proposals/proposal_list.html'
    context_object_name = 'proposals'
    paginate_by = 20

    def get_queryset(self):
        qs = Proposal.objects.select_related('party', 'created_by')
        status = self.request.GET.get('status')
        proposal_type = self.request.GET.get('type')
        search = self.request.GET.get('q')
        if status:
            qs = qs.filter(status=status)
        if proposal_type:
            qs = qs.filter(proposal_type=proposal_type)
        if search:
            from django.db.models import Q
            qs = qs.filter(Q(title__icontains=search) | Q(party__name__icontains=search))
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['status_choices'] = ProposalStatus.choices
        ctx['type_choices'] = ProposalType.choices
        ctx['selected_status'] = self.request.GET.get('status', '')
        ctx['selected_type'] = self.request.GET.get('type', '')
        ctx['search_query'] = self.request.GET.get('q', '')
        return ctx


class ProposalDetailView(LoginRequiredMixin, DetailView):
    model = Proposal
    template_name = 'proposals/proposal_detail.html'
    context_object_name = 'proposal'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['revisions'] = self.object.revisions.select_related('party', 'created_by')
        return ctx


class ProposalCreateView(LoginRequiredMixin, CreateView):
    model = Proposal
    form_class = ProposalForm
    template_name = 'proposals/proposal_form.html'
    success_url = reverse_lazy('proposal-list')

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['action'] = 'New'
        ctx['show_revision_note'] = False
        return ctx


class ProposalUpdateView(LoginRequiredMixin, UpdateView):
    model = Proposal
    form_class = ProposalForm
    template_name = 'proposals/proposal_form.html'

    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        if not obj.is_editable:
            messages.error(self.request, 'Accepted or rejected proposals cannot be edited.')
            # handled by get()
        return obj

    def get(self, request, *args, **kwargs):
        obj = self.get_object()
        if not obj.is_editable:
            return redirect('proposal-detail', pk=obj.pk)
        return super().get(request, *args, **kwargs)

    def form_valid(self, form):
        old = Proposal.objects.get(pk=form.instance.pk)
        revision_note = form.cleaned_data.get('revision_note', '')
        # Snapshot the current (pre-edit) state
        ProposalRevision.objects.create(
            proposal=old,
            version_number=old.current_version,
            title=old.title,
            description=old.description,
            proposal_type=old.proposal_type,
            party=old.party,
            value=old.value,
            currency=old.currency,
            revision_note=revision_note,
            created_by=self.request.user,
        )
        form.instance.current_version = old.current_version + 1
        messages.success(self.request, f'Proposal updated to v{form.instance.current_version}.')
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('proposal-detail', kwargs={'pk': self.object.pk})

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['action'] = 'Edit'
        ctx['show_revision_note'] = True
        return ctx


class ProposalDeleteView(LoginRequiredMixin, DeleteView):
    model = Proposal
    template_name = 'proposals/proposal_confirm_delete.html'
    success_url = reverse_lazy('proposal-list')


class ProposalSendView(LoginRequiredMixin, View):
    def post(self, request, pk):
        proposal = get_object_or_404(Proposal, pk=pk)
        if proposal.status != ProposalStatus.DRAFT:
            messages.error(request, 'Only draft proposals can be marked as sent.')
        else:
            proposal.status = ProposalStatus.SENT
            proposal.save(update_fields=['status'])
            messages.success(request, 'Proposal marked as sent.')
        return redirect('proposal-detail', pk=pk)


class ProposalRejectView(LoginRequiredMixin, View):
    def post(self, request, pk):
        proposal = get_object_or_404(Proposal, pk=pk)
        if proposal.status in (ProposalStatus.ACCEPTED, ProposalStatus.REJECTED):
            messages.error(request, 'Proposal has already been finalised.')
        else:
            proposal.status = ProposalStatus.REJECTED
            proposal.save(update_fields=['status'])
            messages.warning(request, 'Proposal rejected.')
        return redirect('proposal-detail', pk=pk)


class ProposalAcceptView(LoginRequiredMixin, View):
    def post(self, request, pk):
        proposal = get_object_or_404(Proposal, pk=pk)
        if proposal.status in (ProposalStatus.ACCEPTED, ProposalStatus.REJECTED):
            messages.error(request, 'Proposal has already been finalised.')
            return redirect('proposal-detail', pk=pk)

        if proposal.routes_to_tender:
            from tenders.models import Tender
            tender = Tender.objects.create(
                title=proposal.title,
                description=proposal.description,
                party=proposal.party,
                value=proposal.value,
                currency=proposal.currency,
                source_proposal=proposal,
                created_by=request.user,
            )
            proposal.status = ProposalStatus.ACCEPTED
            proposal.save(update_fields=['status'])
            messages.success(request, f'Proposal accepted → Tender "{tender.title}" created.')
            return redirect('tender-detail', pk=tender.pk)

        else:
            from contracts.models import Contract, ContractStatus, ContractType
            from django.utils import timezone
            type_map = {
                ProposalType.SERVIS_SOZLESMESI: ContractType.SERVICE,
                ProposalType.HIZMET_ALIMI:      ContractType.SERVICE,
                ProposalType.SATIN_ALMA:        ContractType.PURCHASE,
                ProposalType.DIGER:             ContractType.OTHER,
            }
            contract = Contract.objects.create(
                title=proposal.title,
                description=proposal.description,
                party=proposal.party,
                contract_type=type_map.get(proposal.proposal_type, ContractType.OTHER),
                status=ContractStatus.ACTIVE,
                start_date=timezone.now().date(),
                value=proposal.value,
                currency=proposal.currency,
                source_proposal=proposal,
                created_by=request.user,
            )
            proposal.status = ProposalStatus.ACCEPTED
            proposal.save(update_fields=['status'])
            messages.success(request, f'Proposal accepted → Contract "{contract.title}" created.')
            return redirect('contract-detail', pk=contract.pk)
