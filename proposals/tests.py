import datetime
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse

from parties.models import Party, PartyType
from .models import Proposal, ProposalRevision, ProposalStatus, ProposalType


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_party(name='Acme Corp'):
    return Party.objects.create(name=name, party_type=PartyType.VENDOR, email='a@acme.com')


def make_proposal(party, **kwargs):
    defaults = dict(
        title='Test Proposal',
        proposal_type=ProposalType.SERVIS_SOZLESMESI,
        status=ProposalStatus.DRAFT,
    )
    defaults.update(kwargs)
    return Proposal.objects.create(party=party, **defaults)


# ---------------------------------------------------------------------------
# Model tests
# ---------------------------------------------------------------------------

class ProposalModelTests(TestCase):
    def setUp(self):
        self.party = make_party()

    def test_str_includes_version(self):
        p = make_proposal(self.party, title='My Proposal')
        self.assertEqual(str(p), 'My Proposal (v1)')

    def test_routes_to_tender_for_ihale(self):
        p = make_proposal(self.party, proposal_type=ProposalType.IHALE)
        self.assertTrue(p.routes_to_tender)

    def test_routes_to_contract_for_other_types(self):
        for ptype in [ProposalType.SERVIS_SOZLESMESI, ProposalType.HIZMET_ALIMI,
                      ProposalType.SATIN_ALMA, ProposalType.DIGER]:
            p = make_proposal(self.party, proposal_type=ptype)
            self.assertFalse(p.routes_to_tender, msg=f'{ptype} should not route to tender')

    def test_is_editable_draft(self):
        p = make_proposal(self.party, status=ProposalStatus.DRAFT)
        self.assertTrue(p.is_editable)

    def test_is_editable_sent(self):
        p = make_proposal(self.party, status=ProposalStatus.SENT)
        self.assertTrue(p.is_editable)

    def test_is_not_editable_accepted(self):
        p = make_proposal(self.party, status=ProposalStatus.ACCEPTED)
        self.assertFalse(p.is_editable)

    def test_is_not_editable_rejected(self):
        p = make_proposal(self.party, status=ProposalStatus.REJECTED)
        self.assertFalse(p.is_editable)

    def test_promoted_object_none_when_no_contract_or_tender(self):
        p = make_proposal(self.party)
        self.assertIsNone(p.promoted_object)

    def test_ordering_newest_first(self):
        make_proposal(self.party, title='First')
        make_proposal(self.party, title='Second')
        titles = list(Proposal.objects.values_list('title', flat=True))
        self.assertEqual(titles[0], 'Second')


class ProposalRevisionModelTests(TestCase):
    def setUp(self):
        self.party = make_party()

    def test_str(self):
        p = make_proposal(self.party, title='My Proposal')
        rev = ProposalRevision.objects.create(
            proposal=p, version_number=1, title='My Proposal',
            proposal_type=ProposalType.SERVIS_SOZLESMESI, party=self.party,
        )
        self.assertEqual(str(rev), 'My Proposal — v1')


# ---------------------------------------------------------------------------
# View tests
# ---------------------------------------------------------------------------

class ProposalViewSetupMixin:
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='testuser', password='testpass')
        self.party = make_party()
        self.client.login(username='testuser', password='testpass')

    def _post_data(self, **kwargs):
        data = dict(
            title='Service Proposal',
            proposal_type=ProposalType.SERVIS_SOZLESMESI,
            party=self.party.pk,
            currency='TRY',
            revision_note='',
        )
        data.update(kwargs)
        return data


class ProposalListViewTests(ProposalViewSetupMixin, TestCase):
    def test_requires_login(self):
        self.client.logout()
        resp = self.client.get(reverse('proposal-list'))
        self.assertEqual(resp.status_code, 302)

    def test_list_ok(self):
        make_proposal(self.party)
        resp = self.client.get(reverse('proposal-list'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Test Proposal')

    def test_filter_by_status(self):
        make_proposal(self.party, title='Draft P', status=ProposalStatus.DRAFT)
        make_proposal(self.party, title='Sent P', status=ProposalStatus.SENT)
        resp = self.client.get(reverse('proposal-list') + '?status=draft')
        self.assertContains(resp, 'Draft P')
        self.assertNotContains(resp, 'Sent P')

    def test_filter_by_type(self):
        make_proposal(self.party, title='Service P', proposal_type=ProposalType.SERVIS_SOZLESMESI)
        make_proposal(self.party, title='Ihale P', proposal_type=ProposalType.IHALE)
        resp = self.client.get(reverse('proposal-list') + '?type=ihale')
        self.assertContains(resp, 'Ihale P')
        self.assertNotContains(resp, 'Service P')

    def test_search(self):
        make_proposal(self.party, title='Alpha Proposal')
        make_proposal(self.party, title='Beta Proposal')
        resp = self.client.get(reverse('proposal-list') + '?q=Alpha')
        self.assertContains(resp, 'Alpha Proposal')
        self.assertNotContains(resp, 'Beta Proposal')


class ProposalDetailViewTests(ProposalViewSetupMixin, TestCase):
    def test_detail_ok(self):
        p = make_proposal(self.party)
        resp = self.client.get(reverse('proposal-detail', args=[p.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Test Proposal')

    def test_404(self):
        resp = self.client.get(reverse('proposal-detail', args=[99999]))
        self.assertEqual(resp.status_code, 404)

    def test_revision_history_shown(self):
        p = make_proposal(self.party)
        ProposalRevision.objects.create(
            proposal=p, version_number=1, title='Old Title',
            proposal_type=ProposalType.SERVIS_SOZLESMESI, party=self.party,
            revision_note='Initial version',
        )
        resp = self.client.get(reverse('proposal-detail', args=[p.pk]))
        self.assertContains(resp, 'Old Title')
        self.assertContains(resp, 'Initial version')


class ProposalCreateViewTests(ProposalViewSetupMixin, TestCase):
    def test_create_get(self):
        resp = self.client.get(reverse('proposal-add'))
        self.assertEqual(resp.status_code, 200)

    def test_create_post(self):
        resp = self.client.post(reverse('proposal-add'), self._post_data())
        self.assertRedirects(resp, reverse('proposal-list'))
        p = Proposal.objects.get(title='Service Proposal')
        self.assertEqual(p.created_by, self.user)
        self.assertEqual(p.current_version, 1)
        self.assertEqual(p.status, ProposalStatus.DRAFT)

    def test_create_invalid(self):
        resp = self.client.post(reverse('proposal-add'), {'currency': 'TRY'})
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(Proposal.objects.exists())


class ProposalUpdateViewTests(ProposalViewSetupMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.proposal = make_proposal(self.party, title='Original Title', value=1000)

    def test_edit_creates_revision(self):
        self.client.post(reverse('proposal-edit', args=[self.proposal.pk]),
                         self._post_data(title='Updated Title', revision_note='Price changed'))
        self.proposal.refresh_from_db()
        self.assertEqual(self.proposal.title, 'Updated Title')
        self.assertEqual(self.proposal.current_version, 2)
        rev = ProposalRevision.objects.get(proposal=self.proposal)
        self.assertEqual(rev.title, 'Original Title')
        self.assertEqual(rev.version_number, 1)
        self.assertEqual(rev.revision_note, 'Price changed')

    def test_accepted_proposal_redirects(self):
        self.proposal.status = ProposalStatus.ACCEPTED
        self.proposal.save()
        resp = self.client.get(reverse('proposal-edit', args=[self.proposal.pk]))
        self.assertRedirects(resp, reverse('proposal-detail', args=[self.proposal.pk]))

    def test_rejected_proposal_redirects(self):
        self.proposal.status = ProposalStatus.REJECTED
        self.proposal.save()
        resp = self.client.get(reverse('proposal-edit', args=[self.proposal.pk]))
        self.assertRedirects(resp, reverse('proposal-detail', args=[self.proposal.pk]))

    def test_multiple_revisions_accumulate(self):
        self.client.post(reverse('proposal-edit', args=[self.proposal.pk]),
                         self._post_data(title='v2'))
        self.client.post(reverse('proposal-edit', args=[self.proposal.pk]),
                         self._post_data(title='v3'))
        self.proposal.refresh_from_db()
        self.assertEqual(self.proposal.current_version, 3)
        self.assertEqual(ProposalRevision.objects.filter(proposal=self.proposal).count(), 2)


class ProposalWorkflowTests(ProposalViewSetupMixin, TestCase):
    def test_send(self):
        p = make_proposal(self.party)
        self.client.post(reverse('proposal-send', args=[p.pk]))
        p.refresh_from_db()
        self.assertEqual(p.status, ProposalStatus.SENT)

    def test_send_only_from_draft(self):
        p = make_proposal(self.party, status=ProposalStatus.SENT)
        self.client.post(reverse('proposal-send', args=[p.pk]))
        p.refresh_from_db()
        self.assertEqual(p.status, ProposalStatus.SENT)  # unchanged

    def test_reject(self):
        p = make_proposal(self.party)
        self.client.post(reverse('proposal-reject', args=[p.pk]))
        p.refresh_from_db()
        self.assertEqual(p.status, ProposalStatus.REJECTED)

    def test_reject_already_accepted_is_noop(self):
        p = make_proposal(self.party, status=ProposalStatus.ACCEPTED)
        self.client.post(reverse('proposal-reject', args=[p.pk]))
        p.refresh_from_db()
        self.assertEqual(p.status, ProposalStatus.ACCEPTED)

    def test_accept_servis_sozlesmesi_creates_contract(self):
        from contracts.models import Contract
        p = make_proposal(self.party, proposal_type=ProposalType.SERVIS_SOZLESMESI, value=5000)
        resp = self.client.post(reverse('proposal-accept', args=[p.pk]))
        p.refresh_from_db()
        self.assertEqual(p.status, ProposalStatus.ACCEPTED)
        contract = Contract.objects.get(source_proposal=p)
        self.assertEqual(contract.title, p.title)
        self.assertRedirects(resp, reverse('contract-detail', args=[contract.pk]))

    def test_accept_hizmet_alimi_creates_contract(self):
        from contracts.models import Contract
        p = make_proposal(self.party, proposal_type=ProposalType.HIZMET_ALIMI)
        self.client.post(reverse('proposal-accept', args=[p.pk]))
        self.assertTrue(Contract.objects.filter(source_proposal=p).exists())

    def test_accept_satin_alma_creates_contract(self):
        from contracts.models import Contract
        p = make_proposal(self.party, proposal_type=ProposalType.SATIN_ALMA)
        self.client.post(reverse('proposal-accept', args=[p.pk]))
        self.assertTrue(Contract.objects.filter(source_proposal=p).exists())

    def test_accept_ihale_creates_tender(self):
        from tenders.models import Tender
        p = make_proposal(self.party, proposal_type=ProposalType.IHALE, value=9000)
        resp = self.client.post(reverse('proposal-accept', args=[p.pk]))
        p.refresh_from_db()
        self.assertEqual(p.status, ProposalStatus.ACCEPTED)
        tender = Tender.objects.get(source_proposal=p)
        self.assertEqual(tender.title, p.title)
        self.assertRedirects(resp, reverse('tender-detail', args=[tender.pk]))

    def test_accept_already_accepted_is_noop(self):
        from contracts.models import Contract
        p = make_proposal(self.party, status=ProposalStatus.ACCEPTED)
        self.client.post(reverse('proposal-accept', args=[p.pk]))
        self.assertFalse(Contract.objects.filter(source_proposal=p).exists())

    def test_contract_links_back_to_proposal(self):
        from contracts.models import Contract
        p = make_proposal(self.party, title='Linked Proposal')
        self.client.post(reverse('proposal-accept', args=[p.pk]))
        contract = Contract.objects.get(source_proposal=p)
        # Access reverse relation
        self.assertEqual(p.contract, contract)

    def test_tender_links_back_to_proposal(self):
        from tenders.models import Tender
        p = make_proposal(self.party, proposal_type=ProposalType.IHALE)
        self.client.post(reverse('proposal-accept', args=[p.pk]))
        tender = Tender.objects.get(source_proposal=p)
        self.assertEqual(p.tender, tender)
