from rest_framework import viewsets,status,filters
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.parsers import JSONParser, FormParser, MultiPartParser
from django.db.models import Q
from django.utils import timezone

from .models import PatientProfile, TREATMENT_TYPES,PATIENT_STATUS
from .serializer import PatientProfileSerializer,PatientCreateSerializer
from accounts.models import User


class PatientViewSet(viewsets.ModelViewSet):
	parser_classes = [JSONParser, FormParser, MultiPartParser]
	queryset=PatientProfile.objects.select_related('user','assigned_doctor').all()
	permission_classes=[IsAuthenticated]

	def get_serializer_class(self):
		if self.action == 'create':
			return PatientCreateSerializer
		return PatientProfileSerializer
	def get_queryset(self):
		qs=PatientProfile.objects.select_related('user','assigned_doctor').all()

		#Search
		search=self.request.query_params.get('search','')
		if search:
			qs=qs.filter(
				Q(user__full_name__icontains=search) |
				Q(user__email__icontains=search) |
				Q(patient_id__icontains=search) |
				Q(phone__icontains=search)
			)
		
		#Filters
		status_f=self.request.query_params.get('status')
		if status_f:
			qs=qs.filter(status=status_f)
		
		treatment=self.request.query_params.get('treatment_type')
		if treatment:
			qs=qs.filter(treatment_type=treatment)
		
		gender=self.request.query_params.get('gender')
		if gender:
			qs=qs.filter(gender=gender)
		
		doctor=self.request.query_params.get('assigned_doctor')
		if doctor:
			qs=qs.filter(assigned_doctor_id=doctor)

		return qs.order_by('-registered_on')
	
	def create(self,request,*args,**kwargs):
		serializer=PatientCreateSerializer(data=request.data)
		serializer.is_valid(raise_exception=True)
		profile=serializer.save()
		return Response(PatientProfileSerializer(profile).data,status=status.HTTP_201_CREATED)
	
	def update(self,request,*args,**kwargs):
		partial=kwargs.pop('partial',True)
		instance=self.get_object()

	#Allow updating assigned doctor by id
		data=request.data.copy()
		serializer=PatientProfileSerializer(instance,data=data,partial=partial)
		serializer.is_valid(raise_exception=True)
		serializer.save()
		return Response(serializer.data)
	
	#--GET /api/patients/<id>/full-profile
	@action(detail=True, methods=['get'],url_path='full-profile')
	def full_profile(self,request,pk=None):
		patient=self.get_objects()
		serializer=PatientProfileSerializer(patient)
		return Response(serializer.data)
	
	#--POST /api/patients/<id>/update-status/
	@action(detail=True,methods=['post'],url_path='update-status')
	def update_status(self,request,pk=None):
		patient=self.get_object()
		new_status=request.data.get('status')
		valid=[s[0] for s in PATIENT_STATUS]

		if new_status not in valid:
			return Response({'detail':f'Invalid status. Choose from {valid}'},status=status.HTTP_400_BAD_REQUEST)
		
		patient.status=new_status
		patient.save()
		return Response({
			'detail':'Status updated.',
			'status':patient.status,
			'display':patient.get_status_display(),
		})
	
	#--POST /api/patients/<id>/link-partner/
	@action(detail=True,methods=['post'],url_path='link-partner')
	def link_partner(self,request,pk=None):
		patient=self.get_object()
		partner_id=request.data.get('partner_id')

		if not partner_id:
			return Response({'detail':'partner_id is required.'},status=status.HTTP_400_BAD_REQUEST)
		try:
			partner=PatientProfile.objects.get(id=partner_id)
		except PatientProfile.DoesNotExist:
			return Response({'detail':'Partner patient not found'},status=status.HTTP_400_BAD_REQUEST)
		if partner.partner_id is not None  and partner.partner_id != patient.id:
			return Response(
				{'detail':f"{partner.user.full_name} is already linked to another patient"},
				status=status.HTTP_400_BAD_REQUEST
			)
		if patient.partner_id is not None and patient.partner_id != partner.id:
			return Response(
				{'detail':f"This patient is already linked to {patient.partner.user.full_name}."},
				status=status.HTTP_400_BAD_REQUEST
			)
		try:
				#link both ways
				patient.partner=partner
				partner.partner=patient
				patient.save()
				partner.save()
				return Response({'detail':f'{patient.user.full_name} successfully linked with {partner.user.full_name}.'})
		except Exception:
			return Response(
				{'detail':"This patient is already linked to another patient."},
				status=status.HTTP_400_BAD_REQUEST
			)


	#--POST /api/patients/<id>/unlink-partner/
	@action(detail=True,methods=['post'],url_path='unlink-partner')
	def unlink_partner(self,request,pk=None):
		patient=self.get_object()
		if patient.partner:
			partner=patient.partner
			partner.partner=None
			patient.partner=None
			patient.save()
			partner.save()
			return Response({'detail':'Partner unlinked.'})
	
	#--GET /api/patients/stats
	@action(detail=False,methods=['get'],url_path='stats')
	def stats(self,request):
		total=PatientProfile.objects.count()
		today=PatientProfile.objects.filter(registered_on=timezone.now().date()).count()
		by_status={
			s[0]: PatientProfile.objects.filter(status=s[0]).count()
			for s in PATIENT_STATUS
		}
		by_treatment={
			t[0]:PatientProfile.objects.filter(treatment_type=t[0]).count()
			for t in TREATMENT_TYPES if PatientProfile.objects.filter(treatment_type=t[0]).exists()
		}
		return Response({
			'total':total,
			'today':today,
			'by_status':by_status,
			'by_treatment':by_treatment
		})
	
	#--GET /api/patients/doctors/
	@action(detail=False,methods=['get'],url_path='doctors')
	def doctors(self,request):
		#available doctors list
		doctors=User.objects.filter(role__in=['GYN','END'],is_active=True)
		return Response([
			{'id':d.id , 'full_name':d.full_name, 'role':d.get_role_display()}
			for d in doctors
		])