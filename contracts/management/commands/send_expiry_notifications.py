"""
Management command to send expiry notifications and auto-expire contracts.

Usage:
    python manage.py send_expiry_notifications
    python manage.py send_expiry_notifications --dry-run
"""
from django.core.management.base import BaseCommand
from django.core.mail import send_mail
from django.utils import timezone
from django.conf import settings
from contracts.models import Contract, ContractStatus


class Command(BaseCommand):
    help = 'Send expiry notifications for contracts expiring soon and mark overdue contracts as expired.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Preview actions without sending emails or saving changes.',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        today = timezone.now().date()
        threshold = getattr(settings, 'EXPIRY_NOTIFICATION_DAYS', 30)
        threshold_date = today + timezone.timedelta(days=threshold)

        # Mark overdue active contracts as expired
        overdue = Contract.objects.filter(
            status=ContractStatus.ACTIVE,
            end_date__lt=today,
        )
        for contract in overdue:
            self.stdout.write(f'[EXPIRED] {contract.title} (ended {contract.end_date})')
            if not dry_run:
                contract.status = ContractStatus.EXPIRED
                contract.save(update_fields=['status'])

        self.stdout.write(f'Marked {overdue.count()} contracts as expired.')

        # Send notifications for contracts expiring soon (not yet notified)
        expiring = Contract.objects.filter(
            status=ContractStatus.ACTIVE,
            end_date__gte=today,
            end_date__lte=threshold_date,
            expiry_notification_sent=False,
        ).select_related('party', 'created_by')

        notified = 0
        for contract in expiring:
            days_left = (contract.end_date - today).days
            subject = f'Contract Expiring Soon: {contract.title}'
            message = (
                f'The following contract is expiring in {days_left} day(s):\n\n'
                f'Title:      {contract.title}\n'
                f'Party:      {contract.party.name}\n'
                f'Type:       {contract.get_contract_type_display()}\n'
                f'End Date:   {contract.end_date}\n'
                f'Value:      {contract.value} {contract.currency}\n\n'
                f'Please review and take action before the contract expires.\n'
            )

            recipient = None
            if contract.created_by and contract.created_by.email:
                recipient = contract.created_by.email
            elif contract.party.email:
                recipient = contract.party.email

            self.stdout.write(
                f'[NOTIFY] {contract.title} — expires in {days_left} day(s)'
                + (f' → {recipient}' if recipient else ' (no email)')
            )

            if not dry_run:
                if recipient:
                    send_mail(
                        subject=subject,
                        message=message,
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        recipient_list=[recipient],
                        fail_silently=True,
                    )
                contract.expiry_notification_sent = True
                contract.save(update_fields=['expiry_notification_sent'])
                notified += 1

        self.stdout.write(
            self.style.SUCCESS(
                f'Done. Expired: {overdue.count()}, Notifications sent: {notified}.'
                + (' (dry run)' if dry_run else '')
            )
        )
