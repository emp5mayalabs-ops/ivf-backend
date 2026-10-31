from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAdminUser
from django.db.models import Sum, Q
from django.core.exceptions import ValidationError, ObjectDoesNotExist

from .models import JournalEntry, JournalEntryLine, Account
from .services import JournalService
from .serializers import (
    JournalEntrySerializer, 
    ProcessBillSerializer, 
    IncomeReportSerializer
)
from .permissions import IsAdminOrBillingStaff  # <-- IMPORT THE CUSTOM PERMISSION


class ProcessBillAPIView(APIView):
    """
    POST /api/finance/process-bill/
    Accepts bills from Pharmacy, Lab, Radiology, etc.
    ALLOWED: Admin, Pharmacy, Lab, Andrology, Radiology staff.
    """
    permission_classes = [IsAdminOrBillingStaff]  # <-- CHANGED: Now allows PHA/TEC/RAD

    def post(self, request):
        serializer = ProcessBillSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        try:
            entry = JournalService.process_bill(
                source_type=data['source_type'],
                source_id=data['source_id'],
                total_amount=data['total_amount'],
                revenue_account_code=data['revenue_account_code'],
                payment_type=data.get('payment_type', 'CASH')
            )
            return Response({
                "message": "Bill processed successfully",
                "journal_entry_id": entry.id
            }, status=status.HTTP_201_CREATED)

        except ObjectDoesNotExist as e:
            return Response({"error": f"Account mapping error: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)
        except ValidationError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class JournalEntryListAPIView(APIView):
    """
    GET /api/finance/journal-entries/?source_type=PHARMACY
    Lists all transactions. ONLY ADMIN USERS CAN ACCESS.
    """
    permission_classes = [IsAdminUser]  # KEPT AS ADMIN ONLY

    def get(self, request):
        queryset = JournalEntry.objects.all().order_by('-entry_date')
        source_type = request.query_params.get('source_type')
        if source_type:
            queryset = queryset.filter(source_type=source_type.upper())
        
        serializer = JournalEntrySerializer(queryset, many=True)
        return Response(serializer.data)


class IncomeReportAPIView(APIView):
    """
    GET /api/finance/income-report/
    Returns Total Income, Total Expenses, Net Profit, and Department breakdown.
    ONLY ADMIN USERS CAN ACCESS.
    """
    permission_classes = [IsAdminUser]  # KEPT AS ADMIN ONLY

    def get(self, request):
        revenue_accounts = Account.objects.filter(type='REVENUE')
        expense_accounts = Account.objects.filter(type='EXPENSE')

        total_income = JournalEntryLine.objects.filter(
            account__in=revenue_accounts,
            is_debit=False
        ).aggregate(total=Sum('amount'))['total'] or 0

        total_expense = JournalEntryLine.objects.filter(
            account__in=expense_accounts,
            is_debit=True
        ).aggregate(total=Sum('amount'))['total'] or 0

        net_profit = total_income - total_expense

        department_data = JournalEntry.objects.values('source_type').annotate(
            total=Sum('lines__amount', filter=Q(lines__account__in=revenue_accounts, lines__is_debit=False))
        ).order_by('-total')

        department_breakdown = {}
        for item in department_data:
            department_breakdown[item['source_type']] = item['total'] or 0

        response_data = {
            "total_income": total_income,
            "total_expense": total_expense,
            "net_profit": net_profit,
            "department_breakdown": department_breakdown,
        }
        return Response(response_data)