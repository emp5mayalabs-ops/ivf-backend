from django.db import models

class Account(models.Model):
    """Chart of Accounts"""
    ACCOUNT_TYPES = [
        ('ASSET', 'Asset'),
        ('LIABILITY', 'Liability'),
        ('EQUITY', 'Equity'),
        ('REVENUE', 'Revenue'),
        ('EXPENSE', 'Expense'),
    ]
    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=100)
    type = models.CharField(max_length=20, choices=ACCOUNT_TYPES)
    is_clearing = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.code} - {self.name}"


class JournalEntry(models.Model):
    """Master record of a transaction"""
    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('POSTED', 'Posted'),
        ('VOID', 'Void'),
    ]
    entry_date = models.DateTimeField(auto_now_add=True)
    description = models.TextField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='POSTED')
    
    source_type = models.CharField(max_length=50, db_index=True)  # PHARMACY, LAB, etc.
    source_id = models.CharField(max_length=100, db_index=True)   # Invoice/ID from source

    class Meta:
        unique_together = ('source_type', 'source_id')

    def __str__(self):
        return f"{self.source_type} - {self.source_id}"


class JournalEntryLine(models.Model):
    """Individual Debit/Credit lines"""
    entry = models.ForeignKey(JournalEntry, on_delete=models.CASCADE, related_name='lines')
    account = models.ForeignKey(Account, on_delete=models.PROTECT)
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    is_debit = models.BooleanField()  # True = Debit, False = Credit

    def __str__(self):
        return f"{'Dr' if self.is_debit else 'Cr'} {self.account.code}: {self.amount}"