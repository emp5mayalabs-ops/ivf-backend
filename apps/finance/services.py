from django.db import transaction
from django.core.exceptions import ValidationError
from .models import Account, JournalEntry, JournalEntryLine

class JournalService:
    
    @staticmethod
    def process_bill(source_type, source_id, total_amount, revenue_account_code, payment_type='CASH'):
        if total_amount <= 0:
            raise ValidationError("Amount must be greater than zero")

        with transaction.atomic():
            clearing_account = Account.objects.get(is_clearing=True)
            
            if payment_type.upper() == 'CASH':
                cash_or_ar_account = Account.objects.get(code='1010')
            else:
                cash_or_ar_account = Account.objects.get(code='2010')

            revenue_account = Account.objects.get(code=revenue_account_code)

            entry = JournalEntry.objects.create(
                description=f"Bill from {source_type} - {source_id}",
                source_type=source_type.upper(),
                source_id=source_id,
                status='POSTED'
            )

            lines_to_create = [
                JournalEntryLine(entry=entry, account=cash_or_ar_account, amount=total_amount, is_debit=True),
                JournalEntryLine(entry=entry, account=clearing_account, amount=total_amount, is_debit=False),
                JournalEntryLine(entry=entry, account=clearing_account, amount=total_amount, is_debit=True),
                JournalEntryLine(entry=entry, account=revenue_account, amount=total_amount, is_debit=False),
            ]
            
            JournalEntryLine.objects.bulk_create(lines_to_create)
            return entry