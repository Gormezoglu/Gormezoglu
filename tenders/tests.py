import datetime
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse

from parties.models import Party, PartyType
from .models import Tender, TenderStatus


def make_party(name='Acme Corp'):
    return Party.objects.create(name=name, party_type=PartyType.VENDOR)


def make_tender(party, **kwargs):
    defaults = dict(title='Test Tender', status=TenderStatus.OPEN, currency='TRY')
    defaults.update(kwargs)
    return Tender.objects.create(party=party, **defaults)


class TenderModelTests(TestCase):
    def setUp(self):
        self.party = make_party()

    def test_str(self):
        t = make_tender(self.party, title='Road Works Tender')
        self.assertEqual(str(t), 'Road Works Tender')

    def test_is_overdue_true(self):
        t = make_tender(self.party, deadline=datetime.date.today() - datetime.timedelta(days=1),
                        status=TenderStatus.OPEN)
        self.assertTrue(t.is_overdue)

    def test_is_overdue_false_future(self):
        t = make_tender(self.party, deadline=datetime.date.today() + datetime.timedelta(days=5))
        self.assertFalse(t.is_overdue)

    def test_is_overdue_false_non_open(self):
        t = make_tender(self.party, deadline=datetime.date.today() - datetime.timedelta(days=1),
                        status=TenderStatus.AWARDED)
        self.assertFalse(t.is_overdue)

    def test_is_overdue_false_no_deadline(self):
        t = make_tender(self.party)
        self.assertFalse(t.is_overdue)

    def test_ordering_newest_first(self):
        make_tender(self.party, title='First')
        make_tender(self.party, title='Second')
        titles = list(Tender.objects.values_list('title', flat=True))
        self.assertEqual(titles[0], 'Second')


class TenderViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='testuser', password='testpass')
        self.party = make_party()
        self.tender = make_tender(self.party)
        self.client.login(username='testuser', password='testpass')

    def _post_data(self, **kwargs):
        data = dict(title='New Tender', party=self.party.pk,
                    status=TenderStatus.OPEN, currency='TRY')
        data.update(kwargs)
        return data

    def test_requires_login(self):
        self.client.logout()
        resp = self.client.get(reverse('tender-list'))
        self.assertEqual(resp.status_code, 302)

    def test_list_ok(self):
        resp = self.client.get(reverse('tender-list'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Test Tender')

    def test_filter_by_status(self):
        make_tender(self.party, title='Open T', status=TenderStatus.OPEN)
        make_tender(self.party, title='Awarded T', status=TenderStatus.AWARDED)
        resp = self.client.get(reverse('tender-list') + '?status=awarded')
        self.assertContains(resp, 'Awarded T')
        self.assertNotContains(resp, 'Open T')

    def test_search(self):
        make_tender(self.party, title='Alpha Tender')
        make_tender(self.party, title='Beta Tender')
        resp = self.client.get(reverse('tender-list') + '?q=Alpha')
        self.assertContains(resp, 'Alpha Tender')
        self.assertNotContains(resp, 'Beta Tender')

    def test_detail_ok(self):
        resp = self.client.get(reverse('tender-detail', args=[self.tender.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Test Tender')

    def test_detail_404(self):
        resp = self.client.get(reverse('tender-detail', args=[99999]))
        self.assertEqual(resp.status_code, 404)

    def test_detail_shows_source_proposal_link(self):
        from proposals.models import Proposal, ProposalType, ProposalStatus
        proposal = Proposal.objects.create(
            title='Source Proposal', party=self.party,
            proposal_type=ProposalType.IHALE, status=ProposalStatus.ACCEPTED,
        )
        self.tender.source_proposal = proposal
        self.tender.save()
        resp = self.client.get(reverse('tender-detail', args=[self.tender.pk]))
        self.assertContains(resp, 'Source Proposal')

    def test_create_get(self):
        resp = self.client.get(reverse('tender-add'))
        self.assertEqual(resp.status_code, 200)

    def test_create_post(self):
        resp = self.client.post(reverse('tender-add'), self._post_data())
        self.assertRedirects(resp, reverse('tender-list'))
        self.assertTrue(Tender.objects.filter(title='New Tender').exists())

    def test_create_sets_created_by(self):
        self.client.post(reverse('tender-add'), self._post_data())
        t = Tender.objects.get(title='New Tender')
        self.assertEqual(t.created_by, self.user)

    def test_update_post(self):
        resp = self.client.post(reverse('tender-edit', args=[self.tender.pk]),
                                self._post_data(title='Updated Tender', status=TenderStatus.EVALUATION))
        self.assertRedirects(resp, reverse('tender-list'))
        self.tender.refresh_from_db()
        self.assertEqual(self.tender.title, 'Updated Tender')
        self.assertEqual(self.tender.status, TenderStatus.EVALUATION)

    def test_delete_post(self):
        pk = self.tender.pk
        resp = self.client.post(reverse('tender-delete', args=[pk]))
        self.assertRedirects(resp, reverse('tender-list'))
        self.assertFalse(Tender.objects.filter(pk=pk).exists())
