# apps/doctor/urls.py - COMPLETE CORRECTED VERSION

from django.urls import path
from .views import (
    DoctorDashboardView, DoctorQueueView, DoctorCompletedPatientsView,
    DoctorPatientsView, DoctorPatientDetailView,
    DoctorAppointmentsView, DoctorClinicalNotesView,
    DoctorPrescriptionsView, DoctorProfileView,
    DoctorCalendarView, DoctorLeaveRequestView,
    DoctorLeaveBalanceView,DoctorMedicineInventoryView,
    DoctorCancelLeaveView,DoctorChangePasswordView,
    DoctorMedicineCategoriesView,
)

urlpatterns = [
    # Dashboard
    path('dashboard/', DoctorDashboardView.as_view(), name='doctor_dashboard'),
    
    # Queue Management
    path('queue/', DoctorQueueView.as_view(), name='doctor_queue'),
    
    # Completed Patients (NEW)
    path('completed/', DoctorCompletedPatientsView.as_view(), name='doctor_completed'),
    
    # Patient Management
    path('patients/', DoctorPatientsView.as_view(), name='doctor_patients'),
    path('patients/<int:patient_id>/', DoctorPatientDetailView.as_view(), name='doctor_patient_detail'),
    
    # Appointments
    path('appointments/', DoctorAppointmentsView.as_view(), name='doctor_appointments'),
    
    # Clinical Notes
    path('notes/', DoctorClinicalNotesView.as_view(), name='doctor_notes'),
    
    # Prescriptions
    path('prescriptions/', DoctorPrescriptionsView.as_view(), name='doctor_prescriptions'),
    
    # Profile
    path('profile/', DoctorProfileView.as_view(), name='doctor_profile'),
    path('change-password/', DoctorChangePasswordView.as_view(), name='doctor_change_password'),

     # Calendar - Doctor's own schedule
    path('calendar/', DoctorCalendarView.as_view(), name='doctor_calendar'),

     #Leave Request URLs
    path('leave/request/', DoctorLeaveRequestView.as_view(), name='doctor_leave_request'),
    path('leave/balance/', DoctorLeaveBalanceView.as_view(), name='doctor_leave_balance'),
    path('leave/cancel/<int:leave_id>/', DoctorCancelLeaveView.as_view(), name='doctor_leave_cancel'),
    # medicine inventory
    path('medicines/', DoctorMedicineInventoryView.as_view(), name='doctor-medicines'),
    path('medicines/<int:id>/', DoctorMedicineInventoryView.as_view(), name='doctor-medicine-detail'),
    path('medicines/categories/', DoctorMedicineCategoriesView.as_view(), name='doctor-medicine-categories'),

]