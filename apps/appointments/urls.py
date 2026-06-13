# apps/appointments/urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    ReceptionistDashboardView,
    OPTicketViewSet,
    ReceptionistPatientViewSet,
    RecentPatientsView,
    # Appointment Management Views
    BookAppointmentView,
    SearchAppointmentView,
    RescheduleAppointmentView,
    CancelAppointmentView,
    DoctorAppointmentCalendarView,
    DailyAppointmentListView,
    WalkInRegistrationView,
    AppointmentDetailView,
    AvailableTimeSlotsView,
)

router = DefaultRouter()
router.register(r'tickets', OPTicketViewSet, basename='rec-ticket')
router.register(r'patients', ReceptionistPatientViewSet, basename='rec-patient')

urlpatterns = [
    # Dashboard and Recent Patients
    path('dashboard/', ReceptionistDashboardView.as_view(), name='receptionist-dashboard'),
    path('recent-patients/', RecentPatientsView.as_view(), name='recent-patients'),
    
    # Include router URLs (tickets and patients)
    path('', include(router.urls)),
    
    # ========== APPOINTMENT MANAGEMENT URLs ==========
    
    # 1. Book Appointment (POST)
    path('appointments/book/', BookAppointmentView.as_view(), name='book-appointment'),
    
    # 2. Search Appointment (GET)
    path('appointments/search/', SearchAppointmentView.as_view(), name='search-appointment'),
    
    # 3. Reschedule Appointment (PATCH)
    path('appointments/reschedule/<int:appointment_id>/', RescheduleAppointmentView.as_view(), name='reschedule-appointment'),
    
    # 4. Cancel Appointment (PATCH)
    path('appointments/cancel/<int:appointment_id>/', CancelAppointmentView.as_view(), name='cancel-appointment'),
    
    # 5. Doctor-wise Appointment Calendar (GET)
    path('appointments/calendar/', DoctorAppointmentCalendarView.as_view(), name='appointment-calendar'),
    path('appointments/calendar/<int:doctor_id>/', DoctorAppointmentCalendarView.as_view(), name='doctor-appointment-calendar'),
    
    # 6. Daily Appointment List (GET)
    path('appointments/daily/', DailyAppointmentListView.as_view(), name='daily-appointments'),
    
    # 7. Walk-in Patient Registration (POST)
    path('appointments/walkin/', WalkInRegistrationView.as_view(), name='walkin-registration'),
    
    # 8. Appointment Details (GET)
    path('appointments/<int:appointment_id>/detail/', AppointmentDetailView.as_view(), name='appointment-detail'),
    
    # 9. Available Time Slots (GET)
    path('appointments/available-slots/', AvailableTimeSlotsView.as_view(), name='available-time-slots'),
]