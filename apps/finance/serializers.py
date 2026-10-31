from rest_framework import serializers
from .models import JournalEntry, JournalEntryLine, Account

class JournalEntryLineSerializer(serializers.ModelSerializer):
    account_code = serializers.CharField(source='account.code', read_only=True)
    account_name = serializers.CharField(source='account.name', read_only=True)

    class Meta:
        model = JournalEntryLine
        fields = ['account_code', 'account_name', 'amount', 'is_debit']


class JournalEntrySerializer(serializers.ModelSerializer):
    lines = JournalEntryLineSerializer(many=True, read_only=True)

    class Meta:
        model = JournalEntry
        fields = ['id', 'entry_date', 'description', 'source_type', 'source_id', 'status', 'lines']


class ProcessBillSerializer(serializers.Serializer):
    """Input validation for processing a bill"""
    source_type = serializers.CharField(max_length=50)
    source_id = serializers.CharField(max_length=100)
    total_amount = serializers.DecimalField(max_digits=15, decimal_places=2)
    revenue_account_code = serializers.CharField(max_length=20)
    payment_type = serializers.CharField(max_length=10, default='CASH')


class IncomeReportSerializer(serializers.Serializer):
    """Output format for the income report"""
    total_income = serializers.DecimalField(max_digits=15, decimal_places=2)
    total_expense = serializers.DecimalField(max_digits=15, decimal_places=2)
    net_profit = serializers.DecimalField(max_digits=15, decimal_places=2)
    department_breakdown = serializers.DictField()