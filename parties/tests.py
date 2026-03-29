from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from .models import Party, PartyType
from .forms import PartyForm


class PartyModelTests(TestCase):
    def setUp(self):
        self.party = Party.objects.create(
            name='Acme Corp',
            party_type=PartyType.VENDOR,
            contact_name='John Doe',
            email='john@acme.com',
            phone='555-1234',
        )

    def test_str(self):
        self.assertEqual(str(self.party), 'Acme Corp (Vendor)')

    def test_total_contract_count_zero(self):
        self.assertEqual(self.party.total_contract_count, 0)

    def test_active_contract_count_zero(self):
        self.assertEqual(self.party.active_contract_count, 0)

    def test_ordering_by_name(self):
        Party.objects.create(name='Zeta Ltd', party_type=PartyType.CUSTOMER)
        Party.objects.create(name='Alpha Inc', party_type=PartyType.PARTNER)
        names = list(Party.objects.values_list('name', flat=True))
        self.assertEqual(names, sorted(names))


class PartyFormTests(TestCase):
    def test_valid_form(self):
        form = PartyForm(data={
            'name': 'Test Party',
            'party_type': PartyType.VENDOR,
            'contact_name': '',
            'email': '',
            'phone': '',
            'address': '',
            'notes': '',
        })
        self.assertTrue(form.is_valid())

    def test_missing_name(self):
        form = PartyForm(data={'party_type': PartyType.VENDOR})
        self.assertFalse(form.is_valid())
        self.assertIn('name', form.errors)

    def test_invalid_email(self):
        form = PartyForm(data={
            'name': 'Test',
            'party_type': PartyType.VENDOR,
            'email': 'not-an-email',
        })
        self.assertFalse(form.is_valid())
        self.assertIn('email', form.errors)


class PartyViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='testuser', password='testpass')
        self.party = Party.objects.create(name='Acme Corp', party_type=PartyType.VENDOR)

    def _login(self):
        self.client.login(username='testuser', password='testpass')

    # --- Auth redirect tests ---
    def test_list_requires_login(self):
        resp = self.client.get(reverse('party-list'))
        self.assertRedirects(resp, '/accounts/login/?next=/parties/')

    def test_detail_requires_login(self):
        resp = self.client.get(reverse('party-detail', args=[self.party.pk]))
        self.assertEqual(resp.status_code, 302)

    def test_create_requires_login(self):
        resp = self.client.get(reverse('party-add'))
        self.assertEqual(resp.status_code, 302)

    # --- List view ---
    def test_list_view(self):
        self._login()
        resp = self.client.get(reverse('party-list'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Acme Corp')

    def test_list_search(self):
        self._login()
        Party.objects.create(name='Beta LLC', party_type=PartyType.CUSTOMER)
        resp = self.client.get(reverse('party-list') + '?q=Acme')
        self.assertContains(resp, 'Acme Corp')
        self.assertNotContains(resp, 'Beta LLC')

    def test_list_filter_by_type(self):
        self._login()
        Party.objects.create(name='Beta LLC', party_type=PartyType.CUSTOMER)
        resp = self.client.get(reverse('party-list') + '?type=vendor')
        self.assertContains(resp, 'Acme Corp')
        self.assertNotContains(resp, 'Beta LLC')

    # --- Detail view ---
    def test_detail_view(self):
        self._login()
        resp = self.client.get(reverse('party-detail', args=[self.party.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Acme Corp')

    def test_detail_404(self):
        self._login()
        resp = self.client.get(reverse('party-detail', args=[99999]))
        self.assertEqual(resp.status_code, 404)

    # --- Create view ---
    def test_create_get(self):
        self._login()
        resp = self.client.get(reverse('party-add'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Add')

    def test_create_post(self):
        self._login()
        resp = self.client.post(reverse('party-add'), {
            'name': 'New Vendor',
            'party_type': PartyType.VENDOR,
            'contact_name': '', 'email': '', 'phone': '', 'address': '', 'notes': '',
        })
        self.assertRedirects(resp, reverse('party-list'))
        self.assertTrue(Party.objects.filter(name='New Vendor').exists())

    def test_create_post_invalid(self):
        self._login()
        resp = self.client.post(reverse('party-add'), {'party_type': PartyType.VENDOR})
        self.assertEqual(resp.status_code, 200)
        self.assertFormError(resp.context['form'], 'name', 'This field is required.')

    # --- Update view ---
    def test_update_post(self):
        self._login()
        resp = self.client.post(reverse('party-edit', args=[self.party.pk]), {
            'name': 'Acme Corp Updated',
            'party_type': PartyType.CUSTOMER,
            'contact_name': '', 'email': '', 'phone': '', 'address': '', 'notes': '',
        })
        self.assertRedirects(resp, reverse('party-list'))
        self.party.refresh_from_db()
        self.assertEqual(self.party.name, 'Acme Corp Updated')
        self.assertEqual(self.party.party_type, PartyType.CUSTOMER)

    # --- Delete view ---
    def test_delete_post(self):
        self._login()
        pk = self.party.pk
        resp = self.client.post(reverse('party-delete', args=[pk]))
        self.assertRedirects(resp, reverse('party-list'))
        self.assertFalse(Party.objects.filter(pk=pk).exists())
