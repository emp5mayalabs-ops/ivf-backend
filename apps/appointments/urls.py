from django.urls import path,include
from rest_framework.routers import DefaultRouter
from .views import ReceptionistDashboardView,OPTicketViewSet,ReceptionistPatientViewSet


router=DefaultRouter()
router.register(r'tickets', OPTicketViewSet,basename='rec-ticket')
router.register(r'patients', ReceptionistPatientViewSet,basename='rec-patient')

urlpatterns=[
	path('dashboard/',ReceptionistDashboardView.as_view()),
    path('',include(router.urls)),
]
