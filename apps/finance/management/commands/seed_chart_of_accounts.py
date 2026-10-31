from django.core.management.base import BaseCommand
from finance.models import Account

class Command(BaseCommand):
    help = 'Seed the Chart of Accounts'

    def handle(self, *args, **kwargs):
        accounts = [
            {'code': '1010', 'name': 'Cash in Hand', 'type': 'ASSET'},
            {'code': '2010', 'name': 'Accounts Receivable', 'type': 'ASSET'},
            {'code': '9999', 'name': 'Inter-Department Clearing', 'type': 'LIABILITY', 'is_clearing': True},
            {'code': '4100', 'name': 'Pharmacy Sales Revenue', 'type': 'REVENUE'},
            {'code': '4200', 'name': 'Lab Test Revenue', 'type': 'REVENUE'},
            {'code': '4300', 'name': 'Radiology Revenue', 'type': 'REVENUE'},
            {'code': '4400', 'name': 'OPD Consultation Revenue', 'type': 'REVENUE'},
            {'code': '5100', 'name': 'Medicine Procurement Cost', 'type': 'EXPENSE'},
            {'code': '5200', 'name': 'Staff Salaries', 'type': 'EXPENSE'},
        ]
        for acc in accounts:
            obj, created = Account.objects.get_or_create(
                code=acc['code'],
                defaults={k: v for k, v in acc.items() if k != 'code'}
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f"Created {acc['code']}"))