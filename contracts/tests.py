import datetime
from io import StringIO
from unittest.mock import patch

from django.test import TestCase, Client, override_settings
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone
from django.core import mail

from parties.models import Party, PartyType
from .models import Contract, ContractStatus, ContractType, ContractPayment, PaymentStatus
from .forms import ContractForm


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_party(name='Acme Corp', party_type=PartyType.VENDOR):
    return Party.objects.create(name=name, party_type=party_type, email='contact@acme.com')


def make_contract(party, **kwargs):
    defaults = dict(
        title='Test Contract',
        contract_type=ContractType.SERVICE,
        status=ContractStatus.ACTIVE,
        start_date=datetime.date.today() - datetime.timedelta(days=30),
        end_date=datetime.date.today() + datetime.timedelta(days=60),
    )
    defaults.update(kwargs)
    return Contract.objects.create(party=party, **defaults)


# ---------------------------------------------------------------------------
# Model tests
# ---------------------------------------------------------------------------

class ContractModelTests(TestCase):
    def setUp(self):
        self.party = make_party()

    def test_str(self):
        c = make_contract(self.party, title='My Contract')
        self.assertEqual(str(c), 'My Contract')

    def test_is_expiring_soon_true(self):
        c = make_contract(self.party, end_date=datetime.date.today() + datetime.timedelta(days=10))
        self.assertTrue(c.is_expiring_soon)

    def test_is_expiring_soon_false_far_future(self):
        c = make_contract(self.party, end_date=datetime.date.today() + datetime.timedelta(days=90))
        self.assertFalse(c.is_expiring_soon)

    def test_is_expiring_soon_false_draft(self):
        c = make_contract(
            self.party,
            status=ContractStatus.DRAFT,
            end_date=datetime.date.today() + datetime.timedelta(days=5),
        )
        self.assertFalse(c.is_expiring_soon)

    def test_is_expiring_soon_false_no_end_date(self):
        c = make_contract(self.party, end_date=None)
        self.assertFalse(c.is_expiring_soon)

    def test_days_until_expiry(self):
        future = datetime.date.today() + datetime.timedelta(days=15)
        c = make_contract(self.party, end_date=future)
        self.assertEqual(c.days_until_expiry, 15)

    def test_days_until_expiry_none(self):
        c = make_contract(self.party, end_date=None)
        self.assertIsNone(c.days_until_expiry)

    def test_is_overdue_true(self):
        c = make_contract(self.party, end_date=datetime.date.today() - datetime.timedelta(days=1))
        self.assertTrue(c.is_overdue)

    def test_is_overdue_false_future(self):
        c = make_contract(self.party)
        self.assertFalse(c.is_overdue)

    def test_is_overdue_false_non_active(self):
        c = make_contract(
            self.party,
            status=ContractStatus.EXPIRED,
            end_date=datetime.date.today() - datetime.timedelta(days=1),
        )
        self.assertFalse(c.is_overdue)

    def test_update_expired_status(self):
        c = make_contract(self.party, end_date=datetime.date.today() - datetime.timedelta(days=1))
        self.assertEqual(c.status, ContractStatus.ACTIVE)
        c.update_expired_status()
        c.refresh_from_db()
        self.assertEqual(c.status, ContractStatus.EXPIRED)

    def test_update_expired_status_not_overdue(self):
        c = make_contract(self.party)
        c.update_expired_status()
        c.refresh_from_db()
        self.assertEqual(c.status, ContractStatus.ACTIVE)

    def test_ordering_newest_first(self):
        c1 = make_contract(self.party, title='First')
        c2 = make_contract(self.party, title='Second')
        contracts = list(Contract.objects.values_list('title', flat=True))
        self.assertEqual(contracts[0], 'Second')


# ---------------------------------------------------------------------------
# Form tests
# ---------------------------------------------------------------------------

class ContractFormTests(TestCase):
    def setUp(self):
        self.party = make_party()

    def _valid_data(self, **kwargs):
        data = dict(
            title='Service Contract',
            contract_type=ContractType.SERVICE,
            status=ContractStatus.DRAFT,
            party=self.party.pk,
            start_date=datetime.date.today(),
            end_date=datetime.date.today() + datetime.timedelta(days=365),
            currency='USD',
        )
        data.update(kwargs)
        return data

    def test_valid_form(self):
        form = ContractForm(data=self._valid_data())
        self.assertTrue(form.is_valid(), form.errors)

    def test_missing_title(self):
        data = self._valid_data()
        del data['title']
        form = ContractForm(data=data)
        self.assertFalse(form.is_valid())
        self.assertIn('title', form.errors)

    def test_end_before_start_invalid(self):
        form = ContractForm(data=self._valid_data(
            start_date=datetime.date.today(),
            end_date=datetime.date.today() - datetime.timedelta(days=1),
        ))
        self.assertFalse(form.is_valid())
        self.assertIn('__all__', form.errors)

    def test_no_end_date_is_valid(self):
        data = self._valid_data()
        data.pop('end_date')
        form = ContractForm(data=data)
        self.assertTrue(form.is_valid(), form.errors)

    def test_same_start_and_end_date_valid(self):
        today = datetime.date.today()
        form = ContractForm(data=self._valid_data(start_date=today, end_date=today))
        self.assertTrue(form.is_valid(), form.errors)


# ---------------------------------------------------------------------------
# View tests
# ---------------------------------------------------------------------------

class DashboardViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='testuser', password='testpass')
        self.party = make_party()

    def _login(self):
        self.client.login(username='testuser', password='testpass')

    def test_redirect_if_not_logged_in(self):
        resp = self.client.get(reverse('dashboard'))
        self.assertRedirects(resp, '/accounts/login/?next=/')

    def test_dashboard_ok(self):
        self._login()
        resp = self.client.get(reverse('dashboard'))
        self.assertEqual(resp.status_code, 200)

    def test_dashboard_stats(self):
        self._login()
        make_contract(self.party, status=ContractStatus.ACTIVE)
        make_contract(self.party, status=ContractStatus.EXPIRED)
        make_contract(self.party, status=ContractStatus.DRAFT)
        resp = self.client.get(reverse('dashboard'))
        self.assertEqual(resp.context['total_contracts'], 3)
        self.assertEqual(resp.context['active_contracts'], 1)
        self.assertEqual(resp.context['expired_contracts'], 1)
        self.assertEqual(resp.context['draft_contracts'], 1)

    def test_expiring_soon_count(self):
        self._login()
        make_contract(self.party, end_date=datetime.date.today() + datetime.timedelta(days=10))
        make_contract(self.party, end_date=datetime.date.today() + datetime.timedelta(days=90))
        resp = self.client.get(reverse('dashboard'))
        self.assertEqual(resp.context['expiring_soon'], 1)


class ContractListViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='testuser', password='testpass')
        self.party = make_party()
        self.client.login(username='testuser', password='testpass')

    def test_list_view(self):
        make_contract(self.party, title='Alpha')
        resp = self.client.get(reverse('contract-list'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Alpha')

    def test_requires_login(self):
        self.client.logout()
        resp = self.client.get(reverse('contract-list'))
        self.assertEqual(resp.status_code, 302)

    def test_filter_by_status(self):
        make_contract(self.party, title='Active One', status=ContractStatus.ACTIVE)
        make_contract(self.party, title='Draft One', status=ContractStatus.DRAFT)
        resp = self.client.get(reverse('contract-list') + '?status=draft')
        self.assertContains(resp, 'Draft One')
        self.assertNotContains(resp, 'Active One')

    def test_filter_by_type(self):
        make_contract(self.party, title='Service C', contract_type=ContractType.SERVICE)
        make_contract(self.party, title='NDA C', contract_type=ContractType.NDA)
        resp = self.client.get(reverse('contract-list') + '?contract_type=nda')
        self.assertContains(resp, 'NDA C')
        self.assertNotContains(resp, 'Service C')

    def test_search(self):
        make_contract(self.party, title='Alpha Contract')
        make_contract(self.party, title='Beta Contract')
        resp = self.client.get(reverse('contract-list') + '?q=Alpha')
        self.assertContains(resp, 'Alpha Contract')
        self.assertNotContains(resp, 'Beta Contract')

    def test_search_by_party_name(self):
        other_party = make_party(name='Delta Corp')
        make_contract(self.party, title='Acme Deal')
        make_contract(other_party, title='Delta Deal')
        resp = self.client.get(reverse('contract-list') + '?q=Delta')
        self.assertContains(resp, 'Delta Deal')
        self.assertNotContains(resp, 'Acme Deal')


class ContractDetailViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='testuser', password='testpass')
        self.party = make_party()
        self.contract = make_contract(self.party)
        self.client.login(username='testuser', password='testpass')

    def test_detail_ok(self):
        resp = self.client.get(reverse('contract-detail', args=[self.contract.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, self.contract.title)

    def test_404(self):
        resp = self.client.get(reverse('contract-detail', args=[99999]))
        self.assertEqual(resp.status_code, 404)

    def test_expiring_soon_alert_shown(self):
        self.contract.end_date = datetime.date.today() + datetime.timedelta(days=5)
        self.contract.save()
        resp = self.client.get(reverse('contract-detail', args=[self.contract.pk]))
        self.assertContains(resp, 'expires in')


class ContractCreateViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='testuser', password='testpass')
        self.party = make_party()
        self.client.login(username='testuser', password='testpass')

    def _post_data(self, **kwargs):
        data = dict(
            title='New Contract',
            contract_type=ContractType.SERVICE,
            status=ContractStatus.DRAFT,
            party=self.party.pk,
            start_date=datetime.date.today(),
            end_date=datetime.date.today() + datetime.timedelta(days=365),
            currency='USD',
        )
        data.update(kwargs)
        return data

    def test_create_get(self):
        resp = self.client.get(reverse('contract-add'))
        self.assertEqual(resp.status_code, 200)

    def test_create_post_success(self):
        resp = self.client.post(reverse('contract-add'), self._post_data())
        c = Contract.objects.get(title='New Contract')
        self.assertRedirects(resp, reverse('contract-detail', args=[c.pk]))
        self.assertTrue(Contract.objects.filter(title='New Contract').exists())

    def test_create_sets_created_by(self):
        self.client.post(reverse('contract-add'), self._post_data())
        c = Contract.objects.get(title='New Contract')
        self.assertEqual(c.created_by, self.user)

    def test_create_invalid(self):
        resp = self.client.post(reverse('contract-add'), {'title': ''})
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(Contract.objects.filter(title='').exists())


class ContractUpdateViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='testuser', password='testpass')
        self.party = make_party()
        self.contract = make_contract(self.party, title='Old Title')
        self.client.login(username='testuser', password='testpass')

    def test_update_post(self):
        resp = self.client.post(reverse('contract-edit', args=[self.contract.pk]), {
            'title': 'Updated Title',
            'contract_type': ContractType.NDA,
            'status': ContractStatus.ACTIVE,
            'party': self.party.pk,
            'start_date': datetime.date.today(),
            'end_date': datetime.date.today() + datetime.timedelta(days=100),
            'currency': 'EUR',
        })
        self.assertRedirects(resp, reverse('contract-detail', args=[self.contract.pk]))
        self.contract.refresh_from_db()
        self.assertEqual(self.contract.title, 'Updated Title')
        self.assertEqual(self.contract.currency, 'EUR')


class ContractDeleteViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='testuser', password='testpass')
        self.party = make_party()
        self.contract = make_contract(self.party)
        self.client.login(username='testuser', password='testpass')

    def test_delete_post(self):
        pk = self.contract.pk
        resp = self.client.post(reverse('contract-delete', args=[pk]))
        self.assertRedirects(resp, reverse('contract-list'))
        self.assertFalse(Contract.objects.filter(pk=pk).exists())

    def test_delete_get_confirmation(self):
        resp = self.client.get(reverse('contract-delete', args=[self.contract.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, self.contract.title)


# ---------------------------------------------------------------------------
# Management command tests
# ---------------------------------------------------------------------------

class SendExpiryNotificationsCommandTests(TestCase):
    def setUp(self):
        self.party = make_party()
        self.user = User.objects.create_user(
            username='manager', password='pass', email='manager@example.com'
        )

    def _run_command(self, dry_run=False):
        from django.core.management import call_command
        out = StringIO()
        args = ['send_expiry_notifications']
        if dry_run:
            args.append('--dry-run')
        call_command(*args, stdout=out)
        return out.getvalue()

    def test_marks_overdue_contracts_expired(self):
        c = make_contract(
            self.party,
            status=ContractStatus.ACTIVE,
            end_date=datetime.date.today() - datetime.timedelta(days=1),
        )
        self._run_command()
        c.refresh_from_db()
        self.assertEqual(c.status, ContractStatus.EXPIRED)

    def test_does_not_expire_future_contracts(self):
        c = make_contract(self.party)
        self._run_command()
        c.refresh_from_db()
        self.assertEqual(c.status, ContractStatus.ACTIVE)

    @override_settings(
        EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
        EXPIRY_NOTIFICATION_DAYS=30,
    )
    def test_sends_notification_email(self):
        c = make_contract(
            self.party,
            end_date=datetime.date.today() + datetime.timedelta(days=10),
            expiry_notification_sent=False,
        )
        c.created_by = self.user
        c.save()
        self._run_command()
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(c.title, mail.outbox[0].subject)

    @override_settings(
        EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
        EXPIRY_NOTIFICATION_DAYS=30,
    )
    def test_marks_notification_sent(self):
        c = make_contract(
            self.party,
            end_date=datetime.date.today() + datetime.timedelta(days=10),
            expiry_notification_sent=False,
        )
        c.created_by = self.user
        c.save()
        self._run_command()
        c.refresh_from_db()
        self.assertTrue(c.expiry_notification_sent)

    @override_settings(
        EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
        EXPIRY_NOTIFICATION_DAYS=30,
    )
    def test_does_not_resend_notification(self):
        c = make_contract(
            self.party,
            end_date=datetime.date.today() + datetime.timedelta(days=10),
            expiry_notification_sent=True,
        )
        c.created_by = self.user
        c.save()
        self._run_command()
        self.assertEqual(len(mail.outbox), 0)

    def test_dry_run_does_not_change_status(self):
        c = make_contract(
            self.party,
            status=ContractStatus.ACTIVE,
            end_date=datetime.date.today() - datetime.timedelta(days=1),
        )
        output = self._run_command(dry_run=True)
        c.refresh_from_db()
        self.assertEqual(c.status, ContractStatus.ACTIVE)
        self.assertIn('dry run', output)

    @override_settings(
        EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
        EXPIRY_NOTIFICATION_DAYS=30,
    )
    def test_dry_run_does_not_send_email(self):
        c = make_contract(
            self.party,
            end_date=datetime.date.today() + datetime.timedelta(days=5),
            expiry_notification_sent=False,
        )
        c.created_by = self.user
        c.save()
        self._run_command(dry_run=True)
        self.assertEqual(len(mail.outbox), 0)

    def test_does_not_notify_contracts_outside_threshold(self):
        c = make_contract(
            self.party,
            end_date=datetime.date.today() + datetime.timedelta(days=90),
            expiry_notification_sent=False,
        )
        c.created_by = self.user
        c.save()
        self._run_command()
        c.refresh_from_db()
        self.assertFalse(c.expiry_notification_sent)

# ---------------------------------------------------------------------------
# ContractPayment model tests
# ---------------------------------------------------------------------------

def make_bakim_contract(party, months=3, **kwargs):
    today = datetime.date.today()
    end = today.replace(day=1)
    # advance by `months` months
    month = end.month - 1 + months
    end = end.replace(year=end.year + month // 12, month=month % 12 + 1)
    defaults = dict(
        title='Bakım Contract',
        contract_type=ContractType.BAKIM_ONARIM,
        status=ContractStatus.ACTIVE,
        start_date=today.replace(day=1),
        end_date=end,
        monthly_payment='1000.00',
        currency='TRY',
    )
    defaults.update(kwargs)
    return Contract.objects.create(party=party, **defaults)


class ContractPaymentModelTests(TestCase):
    def setUp(self):
        self.party = make_party()

    def test_str(self):
        c = make_bakim_contract(self.party)
        c.generate_payment_schedule()
        p = ContractPayment.objects.filter(contract=c).first()
        self.assertIn(c.title, str(p))
        self.assertIn('-', str(p))  # period_label contains YYYY-MM

    def test_is_overdue_true(self):
        c = make_bakim_contract(self.party)
        p = ContractPayment.objects.create(
            contract=c,
            period_label='2020-01',
            due_date=datetime.date(2020, 1, 1),
            amount=1000,
            currency='TRY',
            status=PaymentStatus.PENDING,
        )
        self.assertTrue(p.is_overdue)

    def test_is_overdue_false_paid(self):
        c = make_bakim_contract(self.party)
        p = ContractPayment.objects.create(
            contract=c,
            period_label='2020-01',
            due_date=datetime.date(2020, 1, 1),
            amount=1000,
            currency='TRY',
            status=PaymentStatus.PAID,
        )
        self.assertFalse(p.is_overdue)

    def test_is_overdue_false_future(self):
        c = make_bakim_contract(self.party)
        future = datetime.date.today() + datetime.timedelta(days=30)
        p = ContractPayment.objects.create(
            contract=c,
            period_label=future.strftime('%Y-%m'),
            due_date=future,
            amount=1000,
            currency='TRY',
        )
        self.assertFalse(p.is_overdue)


class GeneratePaymentScheduleTests(TestCase):
    def setUp(self):
        self.party = make_party()

    def test_generates_correct_number_of_payments(self):
        today = datetime.date.today().replace(day=1)
        end = today.replace(month=today.month + 2) if today.month <= 10 else \
              today.replace(year=today.year + 1, month=(today.month + 2) % 12 or 12)
        c = make_bakim_contract(self.party, end_date=end)
        n = c.generate_payment_schedule()
        self.assertGreater(n, 0)
        self.assertEqual(ContractPayment.objects.filter(contract=c).count(), n)

    def test_does_not_duplicate_paid_payments(self):
        c = make_bakim_contract(self.party)
        c.generate_payment_schedule()
        # Mark first payment as paid
        first = ContractPayment.objects.filter(contract=c).order_by('due_date').first()
        first.status = PaymentStatus.PAID
        first.save()
        paid_period = first.period_label
        # Regenerate
        c.generate_payment_schedule()
        # Paid payment must still exist and be unique
        self.assertEqual(ContractPayment.objects.filter(contract=c, period_label=paid_period).count(), 1)
        self.assertEqual(ContractPayment.objects.get(contract=c, period_label=paid_period).status, PaymentStatus.PAID)

    def test_no_payments_for_non_bakim(self):
        c = make_contract(self.party)
        n = c.generate_payment_schedule()
        self.assertEqual(n, 0)
        self.assertEqual(ContractPayment.objects.filter(contract=c).count(), 0)

    def test_no_payments_without_monthly_amount(self):
        c = make_bakim_contract(self.party, monthly_payment=None)
        n = c.generate_payment_schedule()
        self.assertEqual(n, 0)

    def test_unique_period_labels(self):
        c = make_bakim_contract(self.party)
        c.generate_payment_schedule()
        c.generate_payment_schedule()  # second call should not create duplicates
        periods = list(ContractPayment.objects.filter(contract=c).values_list('period_label', flat=True))
        self.assertEqual(len(periods), len(set(periods)))

    def test_create_view_auto_generates_schedule(self):
        client = Client()
        user = User.objects.create_user(username='u', password='p')
        client.login(username='u', password='p')
        today = datetime.date.today().replace(day=1)
        end = today.replace(month=today.month + 1) if today.month < 12 else \
              today.replace(year=today.year + 1, month=1)
        resp = client.post(reverse('contract-add'), {
            'title': 'Auto Schedule',
            'contract_type': ContractType.BAKIM_ONARIM,
            'status': ContractStatus.ACTIVE,
            'party': self.party.pk,
            'start_date': today,
            'end_date': end,
            'monthly_payment': '2500.00',
            'currency': 'TRY',
        })
        c = Contract.objects.get(title='Auto Schedule')
        self.assertGreater(ContractPayment.objects.filter(contract=c).count(), 0)


class PaymentMarkPaidViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='testuser', password='testpass')
        self.party = make_party()
        self.client.login(username='testuser', password='testpass')
        self.contract = make_bakim_contract(self.party)
        self.contract.generate_payment_schedule()
        self.payment = ContractPayment.objects.filter(contract=self.contract).first()

    def test_requires_login(self):
        self.client.logout()
        resp = self.client.post(reverse('payment-pay', args=[self.payment.pk]))
        self.assertEqual(resp.status_code, 302)

    def test_mark_paid(self):
        resp = self.client.post(reverse('payment-pay', args=[self.payment.pk]))
        self.assertRedirects(resp, reverse('contract-detail', args=[self.contract.pk]))
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, PaymentStatus.PAID)
        self.assertEqual(self.payment.paid_date, datetime.date.today())
        self.assertEqual(self.payment.paid_by, self.user)

    def test_mark_paid_with_notes(self):
        self.client.post(reverse('payment-pay', args=[self.payment.pk]), {'notes': 'Wire transfer'})
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.notes, 'Wire transfer')

    def test_cannot_pay_already_paid(self):
        self.payment.status = PaymentStatus.PAID
        self.payment.save()
        self.client.post(reverse('payment-pay', args=[self.payment.pk]))
        # Status should remain PAID (not re-processed)
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, PaymentStatus.PAID)


class PaymentCancelViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='testuser', password='testpass')
        self.party = make_party()
        self.client.login(username='testuser', password='testpass')
        self.contract = make_bakim_contract(self.party)
        self.contract.generate_payment_schedule()
        self.payment = ContractPayment.objects.filter(contract=self.contract).first()

    def test_cancel_pending(self):
        resp = self.client.post(reverse('payment-cancel', args=[self.payment.pk]))
        self.assertRedirects(resp, reverse('contract-detail', args=[self.contract.pk]))
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, PaymentStatus.CANCELLED)

    def test_cannot_cancel_paid(self):
        self.payment.status = PaymentStatus.PAID
        self.payment.save()
        self.client.post(reverse('payment-cancel', args=[self.payment.pk]))
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, PaymentStatus.PAID)


class PaymentOverviewViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='testuser', password='testpass')
        self.party = make_party()
        self.client.login(username='testuser', password='testpass')

    def test_requires_login(self):
        self.client.logout()
        resp = self.client.get(reverse('payment-overview'))
        self.assertEqual(resp.status_code, 302)

    def test_overdue_tab(self):
        c = make_bakim_contract(self.party)
        ContractPayment.objects.create(
            contract=c, period_label='2020-01',
            due_date=datetime.date(2020, 1, 1),
            amount=1000, currency='TRY', status=PaymentStatus.PENDING,
        )
        resp = self.client.get(reverse('payment-overview') + '?tab=overdue')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, '2020-01')

    def test_paid_tab(self):
        c = make_bakim_contract(self.party)
        ContractPayment.objects.create(
            contract=c, period_label='2024-01',
            due_date=datetime.date(2024, 1, 1),
            amount=1000, currency='TRY', status=PaymentStatus.PAID,
            paid_date=datetime.date(2024, 1, 5),
        )
        resp = self.client.get(reverse('payment-overview') + '?tab=paid')
        self.assertContains(resp, '2024-01')

    def test_contract_detail_shows_payment_schedule(self):
        c = make_bakim_contract(self.party)
        c.generate_payment_schedule()
        resp = self.client.get(reverse('contract-detail', args=[c.pk]))
        self.assertContains(resp, 'Monthly Payment Schedule')
        self.assertContains(resp, 'Bekliyor')
