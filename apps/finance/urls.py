from django.urls import path
from .views import ProcessBillAPIView, JournalEntryListAPIView, IncomeReportAPIView

urlpatterns = [
    path('process-bill/', ProcessBillAPIView.as_view(), name='process-bill'),
    path('journal-entries/', JournalEntryListAPIView.as_view(), name='journal-entries'),
    path('income-report/', IncomeReportAPIView.as_view(), name='income-report'),
]