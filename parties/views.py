from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from .models import Party
from .forms import PartyForm


class PartyListView(LoginRequiredMixin, ListView):
    model = Party
    template_name = 'parties/party_list.html'
    context_object_name = 'parties'
    paginate_by = 20

    def get_queryset(self):
        qs = super().get_queryset()
        party_type = self.request.GET.get('type')
        search = self.request.GET.get('q')
        if party_type:
            qs = qs.filter(party_type=party_type)
        if search:
            qs = qs.filter(name__icontains=search)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['party_types'] = Party.party_type.field.choices
        ctx['selected_type'] = self.request.GET.get('type', '')
        ctx['search_query'] = self.request.GET.get('q', '')
        return ctx


class PartyDetailView(LoginRequiredMixin, DetailView):
    model = Party
    template_name = 'parties/party_detail.html'
    context_object_name = 'party'


class PartyCreateView(LoginRequiredMixin, CreateView):
    model = Party
    form_class = PartyForm
    template_name = 'parties/party_form.html'
    success_url = reverse_lazy('party-list')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['action'] = 'Add'
        return ctx


class PartyUpdateView(LoginRequiredMixin, UpdateView):
    model = Party
    form_class = PartyForm
    template_name = 'parties/party_form.html'
    success_url = reverse_lazy('party-list')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['action'] = 'Edit'
        return ctx


class PartyDeleteView(LoginRequiredMixin, DeleteView):
    model = Party
    template_name = 'parties/party_confirm_delete.html'
    success_url = reverse_lazy('party-list')
