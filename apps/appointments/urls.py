from django.urls import path,include
from rest_framework.routers import DefaultRouter
from .views import ReceptionistDashboardView,OPTicketViewSet,ReceptionistPatientViewSet


router=DefaultRouter()
router.register(r'dashboard', ReceptionistDashboardView,basename='rec-dashboard')
router.register(r'tickets', OPTicketViewSet,basename='rec-ticket')
router.register(r'patients', ReceptionistPatientViewSet,basename='rec-patient')

urlpatterns=[
    path('',include(router.urls))
]
