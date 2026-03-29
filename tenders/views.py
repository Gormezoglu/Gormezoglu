from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.db.models import Q

from .models import Tender, TenderStatus
from .forms import TenderForm


class TenderListView(LoginRequiredMixin, ListView):
    model = Tender
    template_name = 'tenders/tender_list.html'
    context_object_name = 'tenders'
    paginate_by = 20

    def get_queryset(self):
        qs = Tender.objects.select_related('party', 'source_proposal')
        status = self.request.GET.get('status')
        search = self.request.GET.get('q')
        if status:
            qs = qs.filter(status=status)
        if search:
            qs = qs.filter(Q(title__icontains=search) | Q(party__name__icontains=search))
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['status_choices'] = TenderStatus.choices
        ctx['selected_status'] = self.request.GET.get('status', '')
        ctx['search_query'] = self.request.GET.get('q', '')
        return ctx


class TenderDetailView(LoginRequiredMixin, DetailView):
    model = Tender
    template_name = 'tenders/tender_detail.html'
    context_object_name = 'tender'


class TenderCreateView(LoginRequiredMixin, CreateView):
    model = Tender
    form_class = TenderForm
    template_name = 'tenders/tender_form.html'
    success_url = reverse_lazy('tender-list')

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['action'] = 'New'
        return ctx


class TenderUpdateView(LoginRequiredMixin, UpdateView):
    model = Tender
    form_class = TenderForm
    template_name = 'tenders/tender_form.html'
    success_url = reverse_lazy('tender-list')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['action'] = 'Edit'
        return ctx


class TenderDeleteView(LoginRequiredMixin, DeleteView):
    model = Tender
    template_name = 'tenders/tender_confirm_delete.html'
    success_url = reverse_lazy('tender-list')
