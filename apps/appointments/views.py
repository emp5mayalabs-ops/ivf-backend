from rest_framework import viewsets,status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.parsers import JSONParser,FormParser,MultiPartParser
from django.utils import timezone
from django.shortcuts import get_object_or_404

from .models import OPTicket
from .serializer import OPTicketSerializer,PatientBasicSerializer,DoctorChoiceSerializer
from .permissions import ReceptionistPermission
from patients.models import PatientProfile
from accounts.models import User
from departments.models import Department

	
class ReceptionistPatientViewSet(viewsets.ModelViewSet):
	permission_classes=[ReceptionistPermission]
	parser_classes=[JSONParser,FormParser,MultiPartParser]
	serializer_class=PatientBasicSerializer
	http_method_names=['get','patch','head','options']
	def get_queryset(self):
		qs=PatientProfile.objects.select_related('user','assigned_doctor').order_by('-registered_on')
		search=self.request.query_params.get('search','')
		stat=self.request.query_params.get('status','')
		if search:
			qs=(
				qs.filter(user__full_name__icontains=search) |
				qs.filter(patient_id__icontains=search) |
				qs.filter(user__email__icontains=search) |
				qs.filter(phone__icontains=search)
            )
		if stat:
			qs=qs.filter(status=stat)
		return qs.distinct()
	@action(detail=True, methods=['get'], url_path='tickets')
	def patient_tickets(self,request,pk=None):
		patient=self.get_object()
		tickets=OPTicket.objects.filter(patient=patient).select_related('assigned_doctor','department','created_by').order_by('-date','-token_number')
		serializer=OPTicketSerializer(tickets,many=True)
		return Response({
			'patient_id':patient.patient_id,
			'count':tickets.count(),
			'tickets':serializer.data,
        })				
    
class OPTicketViewSet(viewsets.ModelViewSet):
	permission_classes=[ReceptionistPermission]
	parser_classes=[JSONParser,FormParser,MultiPartParser]
	serializer_class=OPTicketSerializer
	http_method_names=['get','post','patch','head','options']
	def get_queryset(self):
		qs=OPTicket.objects.select_related(
		    'patient__user','assigned_doctor','department','created_by'
        )
		date=self.request.query_params.get('date','')
		stat=self.request.query_params.get('status','')
		dept=self.request.query_params.get('department','')
		if date:
			qs=qs.filter(date=date)
		else:
		    qs=qs.filter(date=timezone.now().date())
		if stat:
		    qs=qs.filter(status=stat)
		if dept:
			qs=qs.filter(department_id=dept)
		return qs.order_by('token_number')

	def get_serializer_context(self):
		ctx=super().get_serializer_context()
		ctx['request']=self.request
		return ctx
	@action(detail=False, methods=['get'], url_path='today') 
	def today(self,request):
		today=timezone.now().date()
		tickets=OPTicket.objects.filter(date=today).select_related('patient__user','assigned_doctor','department').order_by('token_number')
		summary={
			'total':tickets.count(),
			'waiting':tickets.filter(status='WAITING').count(),
			'in_consult':tickets.filter(status='IN_CONSULT').count(),
			'done':tickets.filter(status='DONE').count(),
			'cancelled':tickets.filter(status='CANCELLED').count(),
			'next_token':OPTicket.next_token_for_today(),
        }
		serializer=OPTicketSerializer(tickets,many=True)
		return Response({'date':str(today),'summary':summary,'tickets':serializer.data})
	@action(detail=True,methods=['patch'],url_path='status')
	def update_status(self,request,pk=None):
		ticket=self.get_object()
		new_status=request.data.get('status')
		if new_status not in dict(OPTicket.STATUS_CHOICES):
			return Response({'detail':'Invalid status'},status=400)
		ticket.status=new_status
		ticket.save()
		return Response(OPTicketSerializer(ticket).data)
	@action(detail=False,methods=['get'],url_path='doctors')
	def doctors(self,request):
		doctors=User.objects.filter(
			role__in=['END','GYN','ANE'],is_active=True
        ).order_by('full_name')
		return Response(DoctorChoiceSerializer(doctors,many=True).data)
	@action(detail=False,methods=['get'],url_path='departments')
	def departments(self,request):
		depts=Department.objects.filter(is_active=True).values('id','name','code')
		return Response(list(depts))

class ReceptionistDashboardView(viewsets.ViewSet):
	permission_classes=[ReceptionistPermission]
	@action(detail=False,methods=['get'],url_path='')
	def dashboard(self,request):
		today=timezone.now().date()
		patients_today=PatientProfile.objects.filter(date=today)
		today_tickets=OPTicket.objects.filter(date=today)
		tickets_today=today_tickets.count()
		waiting=today_tickets.filter(status='WAITING').count()
		in_consult=today_tickets.filter(status='IN_CONSULT').count()
		done=today_tickets.filter(status='DONE').count()
		cancelled=today_tickets.filter(status='CANCELLED').count()
		next_token=OPTicket.next_token_for_today()
		total_patients=PatientProfile.objects.count()
		recent_patients=PatientProfile.objects.filter(registered_on__date=today).select_related('user').order_by('-registered_on')[:8]
		recent_list=[
			{
				'full_name':p.user.full_name,
				'patient_id':p.patient_id,
				'registered_on':p.registered_on.isoformat() if p.registered_on else None,
            }
			for p in recent_patients
        ]
		return Response({
			'receptionist_name':request.user.full_name,
			'patients_today':patients_today,
			'tickets_today':tickets_today,
			'waiting':waiting,
			'in_consult':in_consult,
			'done':done,
			'cancelled':cancelled,
			'next_token':next_token,
			'total_patients':total_patients,
			'recent_patients':recent_list,
        })















# def create(self,request,*args,**kwargs):
#         response=super().create(request,*args,**kwargs)
#         return response