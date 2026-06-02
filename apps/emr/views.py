from rest_framework import viewsets,status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser,FormParser,JSONParser
from rest_framework.response import Response
from django.shortcuts import get_object_or_404

from .models import (
	EMRRecord,ROLE_ALLOWED_RECORD_TYPES,RECORD_TYPE,ConsultationNote,Diagnosis,Prescription,LabResult,ScanReport,ProcedureNote,TreatmentCycle,NursingNote,PharmacyNote,AndrologyNote,CounsellingNote,MedicalHistoryDocument,
)

from .serializer import (
	EMRRecordListSerializer,EMRRecordDetailSerializer,EMRRecordCreateSerializer,EMRRecordUpdateSerializer,ConsultationNoteSerializer,DiagnosisSerializer,PrescriptionSerializer,LabResultSerializer,ScanReportSerializer,ProcedureNoteSerializer,TreatmentCycleSerializer,NursingNoteSerializer,PharmacyNoteSerializer,AndrologyNoteSerializer,CounsellingNoteSerializer,MedicalHistoryDocumentSerializer
)
from patients.models import PatientProfile

#Permissions helper

ROLE_WITH_EMR_ACCESS=['REC','CCO','FCO','END','GYN','ANE','EMB','NUR','PHA','TEC','AND','ADM']

class EMRPermission(IsAuthenticated):
	def has_permission(self, request, view):
		if not super().has_permission(request, view):
			return False
		return request.user.role in ROLE_WITH_EMR_ACCESS
	
#EMR Record Viewset

class PatientEMRViewset(viewsets.ViewSet):
	permission_classes=[EMRPermission]
	parser_classes=[MultiPartParser,FormParser,JSONParser]

	def get_patient(self,patient_id):
		return get_object_or_404(PatientProfile,id=patient_id)
	
	@action(detail=False, methods=['get'], url_path='dashboard-stats')
	def dashboard_stats(self, request):
		total_patients = PatientProfile.objects.count()
		active_treatments = PatientProfile.objects.filter(status='ACT').count()
		on_hold = PatientProfile.objects.filter(status='HOL').count()
		completed = PatientProfile.objects.filter(status='COM').count()
		
		recent_qs = PatientProfile.objects.select_related('user', 'assigned_doctor').order_by('-updated_on')[:5]
		recent_patients = []
		for p in recent_qs:
			recent_patients.append({
				"id": p.id,
				"patient_id": p.patient_id,
				"full_name": p.user.full_name if p.user else "",
				"last_viewed": p.updated_on.isoformat() if p.updated_on else None,
				"doctor_name": p.assigned_doctor.full_name if p.assigned_doctor else None
			})
			
		return Response({
			"clinic_stats": {
				"total_patients": total_patients,
				"active_treatments": active_treatments,
				"on_hold": on_hold,
				"completed": completed,
				"today_visits": 8,
				"pending_appointments": 12,			
			},
			"recent_patients": recent_patients
		})

	
	@action(detail=False, methods=['get'],url_path='patient/(?P<patient_id>[^/.]+)')
	def patient_summary(self,request,patient_id=None):
		patient=self.get_patient(patient_id)
		records=EMRRecord.objects.filter(patient=patient).select_related('created_by')
		type_counts = {}
		for rt_code,rt_label in RECORD_TYPE:
			count=records.filter(record_type=rt_code).count()
			if count>0:
				type_counts[rt_code] = {'label':rt_label,'count':count}
		
		latest={}
		for rt_code in type_counts:
			rec=records.filter(record_type=rt_code).order_by('-date').first()
			if rec:
				latest[rt_code] = {
					'id':rec.id,
					'title':rec.title,
					'date':str(rec.date),
					'by':rec.created_by.full_name if rec.created_by else None,
				}
		history_count=MedicalHistoryDocument.objects.filter(patient=patient).count()
		return Response({
			'patient':{
				'id': patient.id,
				'patient_id':patient.patient_id,
				'full_name':patient.user.full_name,
				'email':patient.user.email,
				'treatment':patient.treatment_type,
				'status':patient.status,
			},
			'total_records':records.count(),
			'history_documents':history_count,
			'by_type':type_counts,
			'latest_by_type':latest,
		})

	@action(detail=False, methods=['get'], url_path='patient/(?P<patient_id>[^/.]+)/records')
	def patient_records(self,request,patient_id=None):
		patient=self.get_patient(patient_id)
		qs=EMRRecord.objects.filter(patient=patient).select_related('created_by')
		record_type=request.query_params.get('record_type')
		date_from=request.query_params.get('date_from')
		date_to=request.query_params.get('date_to')
		creator_role=request.query_params.get('creator_role')

		if record_type:
			qs=qs.filter(record_type=record_type)
		if date_from:
			qs=qs.filter(date__gte=date_from)
		if date_to:
			qs=qs.filter(date__lte=date_to)
		if creator_role:
			qs=qs.filter(created_by__role=creator_role)

		serializer=EMRRecordListSerializer(qs.order_by('date','-created_at'),many=True)
		return Response({
			'patient_id':patient.patient_id,
			'count':qs.count(),
			'records':serializer.data,
		})

	@action(detail=False,methods=['post'],url_path='patient/(?P<patient_id>[^/.]+)/records/add')
	def add_record(self,request, patient_id=None):
		patient=self.get_patient(patient_id)
		data=request.data.copy()
		data['patient']=patient.id
		serializer=EMRRecordCreateSerializer(data=data, context={'request':request})

		if serializer.is_valid():
			record=serializer.save()
			return Response(EMRRecordDetailSerializer(record,context={'request':request}).data, status=status.HTTP_201_CREATED,)
		return Response(serializer.errors,status=status.HTTP_400_BAD_REQUEST)
	
	@action(detail=False, methods=['get'],url_path='patient/(?P<patient_id>[^/.]+)/records/(?P<record_id>[^/.]+)')
	def record_detail(self,request,patient_id=None,record_id=None):
		patient=self.get_patient(patient_id)
		record=get_object_or_404(EMRRecord,id=record_id,patient=patient)
		serializer=EMRRecordDetailSerializer(record,context={'request':request})
		return Response(serializer.data)
	
	@action(detail=False,methods=['delete'],url_path='patient/(?P<patient_id>[^/.]+)/records/(?P<record_id>[^/.]+)/delete')
	def delete_record(self,request,patient_id=None,record_id=None):
		patient=self.get_patient(patient_id)
		record=get_object_or_404(EMRRecord,id=record_id,patient=patient)
		if request.user.role !='ADM' and record.created_by != request.user:
			return Response({'detail':'Permission denied.'},status=403)
		record.delete()
		return Response({'detail':'Record deleted.'},status=204)
	
	@action(detail=False,methods=['get'],url_path='patient/(?P<patient_id>[^/.]+)/history')
	def patient_history(self,request,patient_id=None):
		patient=self.get_patient(patient_id)
		qs=MedicalHistoryDocument.objects.filter(patient=patient).select_related('uploaded_by')
		doc_type=request.query_params.get('document_type')
		if doc_type:
			qs=qs.filter(document_type=doc_type)
		serializer=MedicalHistoryDocumentSerializer(qs,many=True,context={'request':request})
		return Response({'patient_id':patient.patient_id,'count':qs.count(),'documents':serializer.data})
	
	@action(detail=False,methods=['post'],url_path='patient/(?P<patient_id>[^/.]+)/history/add')
	def add_history_document(self,request,patient_id=None):
		patient=self.get_patient(patient_id)
		data=request.data.copy()
		data['patient']=patient.id
		serializer=MedicalHistoryDocumentSerializer(data=data,context={'request':request})
		if serializer.is_valid():
			serializer.save()
			return Response(serializer.data,status=201)
		return Response(serializer.errors,status=400)
	
	@action(detail=False, methods=['delete'],url_path='history/(?P<doc_id>[^/.]+)/delete')
	def delete_history_document(self,request,doc_id=None):
		doc=get_object_or_404(MedicalHistoryDocument, id=doc_id)
		if request.user.role!='ADM' and doc.uploaded_by!=request.user:
			return Response({'detail':'PErmission denied.'},status=403)
		doc.delete()
		return Response({'detail':'Deleted'},status=204)
	
	@action(detail=False, methods=['get'], url_path='allowed-types')
	def allowed_types(self,request):
		allowed=ROLE_ALLOWED_RECORD_TYPES.get(request.user.role, [])
		types=[{'value':code, 'label':label} for code, label in RECORD_TYPE if code in allowed]
		return Response({'role':request.user.role, 'allowed_types':types})
	
	@action(detail=False,methods=['get'],url_path='patient/(?P<patient_id>[^/.]+)/records/(?P<record_id>[^/.]+)/edit')
	def get_record_for_edit(self,request,patient_id=None,record_id=None):

		patient=self.get_patient(patient_id)
		record=get_object_or_404(EMRRecord,id=record_id,patient=patient)

		if request.user.role!='ADM' and record.created_by != request.user :
			return Response({'detail':'Permission Denied'},status=status.HTTP_403_FORBIDDEN)
		
		serializer=EMRRecordDetailSerializer(record,context={'request':request})
		return Response(serializer.data)
	
	@action(detail=False,methods=['patch'],url_path='patient/(?P<patient_id>[^/.]+)/records/(?P<record_id>[^/.]+)/update')
	def update_record(self,request,patient_id=None,record_id=None):
		patient=self.get_patient(patient_id)
		record=get_object_or_404(EMRRecord,id=record_id,patient=patient)
		if request.user.role != 'ADM' and record.created_by != request.user:
			return Response({'detail': 'Permission denied.'}, status=403)
		data = request.data
		# --- Update base record fields ---
		base_fields = {k: data[k] for k in ['title', 'date', 'notes'] if k in data}
		if base_fields:
			base_serializer = EMRRecordUpdateSerializer(record, data=base_fields, partial=True)
			base_serializer.is_valid(raise_exception=True)
			base_serializer.save()
		errors = {}
		# --- OneToOne sub-sections ---
		one_to_one_map = {
      'consultation':     ('consultation_data',    ConsultationNoteSerializer,  ConsultationNote,  'consultation'),
      'cycle':            ('cycle_data',           TreatmentCycleSerializer,    TreatmentCycle,    'cycle'),
      'nursing_note':     ('nursing_note_data',    NursingNoteSerializer,       NursingNote,       'nursing_note'),
      'pharmacy_note':    ('pharmacy_note_data',   PharmacyNoteSerializer,      PharmacyNote,      'pharmacy_note'),
      'andrology_note':   ('andrology_note_data',  AndrologyNoteSerializer,     AndrologyNote,     'andrology_note'),
      'counselling_note': ('counselling_note_data',CounsellingNoteSerializer,   CounsellingNote,   'counselling_note'),
		}
		
		for related_name, (data_key, SerializerClass, Model, accessor) in one_to_one_map.items():
			if data_key not in data:
				continue
			section_data = data[data_key]
			try:
				instance = getattr(record, accessor)  # exists → update
				s = SerializerClass(instance, data=section_data, partial=True)
			except Model.DoesNotExist:
				instance = None
				s = SerializerClass(data=section_data)
			if s.is_valid():
				if instance:
					s.save()
				else:
					s.save(record=record)
			else:
				errors[data_key] = s.errors
    # --- FK / many sub-sections (replace strategy) ---
    # For diagnosis, prescriptions, lab_results, scans, procedures:
    # send the full updated list → old ones are deleted, new ones created.
    # This is the safest approach for FK sub-sections with no separate IDs on frontend.
		many_map = {
      'diagnosis_data':    (DiagnosisSerializer,    Diagnosis,    'diagnosis'),
      'prescription_data': (PrescriptionSerializer, Prescription, 'prescriptions'),
      'lab_result_data':   (LabResultSerializer,    LabResult,    'lab_results'),
      'scan_data':         (ScanReportSerializer,   ScanReport,   'scans'),
      'procedure_data':    (ProcedureNoteSerializer, ProcedureNote, 'procedures'),
    }
		for data_key, (SerializerClass, Model, related_name) in many_map.items():
			if data_key not in data:
				continue  # not sent → don't touch it
			items = data[data_key]  # full replacement list
			section_errors = []
			valid_instances = []
			for item in items:
				item_id = item.get('id')
				if item_id:
					try:
						instance = Model.objects.get(id=item_id, record=record)
						s = SerializerClass(instance, data=item, partial=True)
					except Model.DoesNotExist:
						section_errors.append({'id': item_id, 'detail': 'Not found.'})
						continue
				else:
					s = SerializerClass(data=item)
					
					if s.is_valid():
						valid_instances.append((s, item_id))
					else:
						section_errors.append(s.errors)
				if section_errors:
					errors[data_key] = section_errors
				else:
					for s, item_id in valid_instances:
						if item_id:
							s.save()
						else:
							s.save(record=record)
		if errors:
			return Response({'detail': 'Partial update errors.', 'errors': errors}, status=400)
		# Return full updated record
		record.refresh_from_db()
		return Response(EMRRecordDetailSerializer(record, context={'request': request}).data)
	
	@action(detail=False, methods=['get'], url_path='records/statistics')
	def records_statistics(self, request):
		"""
		Get comprehensive record statistics:
		- Today
		- This Week
		- This Month
		- This Year
		- Total
		- By Record Type
		"""
		from datetime import datetime, timedelta
		from django.utils import timezone
		from django.db.models import Count, Q

		now = timezone.now()
		today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
		week_start = now - timedelta(days=now.weekday())  # Monday
		week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
		month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
		year_start = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)

		# Base queryset - all records
		base_queryset = EMRRecord.objects.all()

		# Apply role-based filtering if needed
		if request.user.role != 'ADM':
			base_queryset = base_queryset.filter(created_by=request.user)

		# Get counts - Changed 'created_date' to 'created_at'
		statistics = {
			'today': base_queryset.filter(created_at__gte=today_start).count(),
			'this_week': base_queryset.filter(created_at__gte=week_start).count(),
			'this_month': base_queryset.filter(created_at__gte=month_start).count(),
			'this_year': base_queryset.filter(created_at__gte=year_start).count(),
			'total': base_queryset.count(),

			# Get counts by record type
			'by_record_type': base_queryset.values('record_type').annotate(
				count=Count('id')
			).order_by('-count'),

			# Last 7 days trend
			'last_7_days': [],

			# Records by status
			'by_status': base_queryset.values('patient__status').annotate(
				count=Count('id')
			),
		}

		# Calculate last 7 days trend (for chart) - Changed 'created_date' to 'created_at'
		for i in range(6, -1, -1):
			day_start = now - timedelta(days=i)
			day_start = day_start.replace(hour=0, minute=0, second=0, microsecond=0)
			day_end = day_start + timedelta(days=1)

			count = base_queryset.filter(
				created_at__gte=day_start,
				created_at__lt=day_end
			).count()

			statistics['last_7_days'].append({
				'date': day_start.strftime('%Y-%m-%d'),
				'day_name': day_start.strftime('%A'),
				'count': count
			})

		return Response(statistics)

	# Add this inside your PatientEMRViewset class

	@action(detail=False, methods=['get'], url_path='all-records')
	def all_records(self, request):
	    """
	    Load all EMR records across all patients with essential information:
	    - Patient ID
	    - Patient name
	    - Doctor
	    - Type
	    - Created date
	    - Status
	    - Last updated
    
	    Query Parameters:
	    - record_type: Filter by record type (e.g., LAB_RESULT, NURSING_NOTE)
	    - patient_id: Filter by patient ID (partial match)
	    - patient_name: Filter by patient name (partial match)
	    - doctor_name: Filter by doctor name (partial match)
	    - status: Filter by status (completed, today, scheduled, draft)
	    - date_from: Filter by record date from (YYYY-MM-DD)
	    - date_to: Filter by record date to (YYYY-MM-DD)
	    - created_from: Filter by created date from (YYYY-MM-DD)
	    - created_to: Filter by created date to (YYYY-MM-DD)
	    - search: Search in title and notes
	    - ordering: Sort by field (default: -created_at)
	    - page: Page number (default: 1)
	    - page_size: Items per page (default: 50, max: 200)
	    """
	    from datetime import date
	    from django.db.models import Q, F, Value, CharField
	    from django.db.models.functions import Concat
    
	    # Start with all records, select related to avoid N+1 queries
	    qs = EMRRecord.objects.select_related(
	        'patient', 
	        'created_by',
	        'patient__user',  # Assuming patient has user relation
	        'consultation'
	    ).prefetch_related(
	        'procedures'
	    ).all()
    
	    # Apply role-based filtering
	    if request.user.role != 'ADM':
	        qs = qs.filter(created_by=request.user)
    
	    # --- Apply Filters ---
    
	    # Filter by record type
	    record_type = request.query_params.get('record_type')
	    if record_type:
	        qs = qs.filter(record_type=record_type)
    
	    # Filter by patient ID
	    patient_id = request.query_params.get('patient_id')
	    if patient_id:
	        qs = qs.filter(patient__patient_id__icontains=patient_id)
    
	    # Filter by patient name (search in user full_name)
	    patient_name = request.query_params.get('patient_name')
	    if patient_name:
	        qs = qs.filter(
	            Q(patient__user__full_name__icontains=patient_name) |
	            Q(patient__user__first_name__icontains=patient_name) |
	            Q(patient__user__last_name__icontains=patient_name)
	        )
    
	    # Filter by doctor name
	    doctor_name = request.query_params.get('doctor_name')
	    if doctor_name:
	        doctor_filter = Q()
        
	        # Check consultation doctor (if consultation exists with doctor relation)
	        doctor_filter |= Q(consultation__doctor__full_name__icontains=doctor_name)
	        doctor_filter |= Q(consultation__doctor__first_name__icontains=doctor_name)
	        doctor_filter |= Q(consultation__doctor__last_name__icontains=doctor_name)
        
	        # Check procedure performed_by
	        doctor_filter |= Q(procedures__performed_by__full_name__icontains=doctor_name)
        
	        # Check created_by if role is doctor
	        doctor_filter |= Q(created_by__full_name__icontains=doctor_name, created_by__role='DOC')
        
	        qs = qs.filter(doctor_filter).distinct()
    
	    # Filter by status
	    status_filter = request.query_params.get('status')
	    if status_filter:
	        today = date.today()
	        if status_filter.lower() == 'completed':
	            qs = qs.filter(date__lt=today)
	        elif status_filter.lower() == 'today':
	            qs = qs.filter(date=today)
	        elif status_filter.lower() == 'scheduled':
	            qs = qs.filter(date__gt=today)
	        elif status_filter.lower() == 'draft':
	            qs = qs.filter(date__isnull=True)
    
	    # Filter by record date range
	    date_from = request.query_params.get('date_from')
	    if date_from:
	        qs = qs.filter(date__gte=date_from)
    
	    date_to = request.query_params.get('date_to')
	    if date_to:
	        qs = qs.filter(date__lte=date_to)
    
	    # Filter by created date range
	    created_from = request.query_params.get('created_from')
	    if created_from:
	        qs = qs.filter(created_at__date__gte=created_from)
    
	    created_to = request.query_params.get('created_to')
	    if created_to:
	        qs = qs.filter(created_at__date__lte=created_to)
    
	    # Search in title and notes
	    search_term = request.query_params.get('search')
	    if search_term:
	        qs = qs.filter(
	            Q(title__icontains=search_term) |
	            Q(notes__icontains=search_term)
	        )
    
	    # Apply ordering
	    ordering = request.query_params.get('ordering', '-created_at')
	    allowed_orderings = [
	        'created_at', '-created_at', 
	        'updated_at', '-updated_at',
	        'date', '-date',
	        'patient__patient_id', '-patient__patient_id',
	        'record_type', '-record_type'
	    ]
	    if ordering in allowed_orderings:
	        qs = qs.order_by(ordering)
	    else:
	        qs = qs.order_by('-created_at')
    
	    # Get total count before pagination
	    total_count = qs.count()
    
	    # --- Pagination ---
	    try:
	        page = int(request.query_params.get('page', 1))
	        page_size = int(request.query_params.get('page_size', 50))
	        if page_size > 200:
	            page_size = 200  # Limit max page size
	        if page_size < 1:
	            page_size = 50
            
	        start = (page - 1) * page_size
	        end = start + page_size
	        paginated_qs = qs[start:end]
	    except (ValueError, TypeError):
	        page = 1
	        page_size = 50
	        paginated_qs = qs[:50]
    
	    # --- Build Response Data ---
	    records_data = []
	    for record in paginated_qs:
	        # Get patient name
	        patient_name_value = "N/A"
	        if record.patient and hasattr(record.patient, 'user') and record.patient.user:
	            patient_name_value = record.patient.user.full_name or f"{record.patient.user.first_name} {record.patient.user.last_name}".strip()
        
	        # Get doctor name
	        doctor_name_value = "Not Assigned"
	        # Try to get from consultation
	        if hasattr(record, 'consultation') and record.consultation:
	            if hasattr(record.consultation, 'doctor') and record.consultation.doctor:
	                doctor_name_value = record.consultation.doctor.full_name or str(record.consultation.doctor)
	        # Try from procedures
	        elif hasattr(record, 'procedures') and record.procedures.exists():
	            procedure = record.procedures.first()
	            if hasattr(procedure, 'performed_by') and procedure.performed_by:
	                doctor_name_value = procedure.performed_by.full_name or str(procedure.performed_by)
	        # Fallback to created_by if they are a doctor
	        elif record.created_by and hasattr(record.created_by, 'role') and record.created_by.role == 'DOC':
	            doctor_name_value = record.created_by.full_name or str(record.created_by)
        
	        # Determine status
	        today = date.today()
	        if not record.date:
	            status_value = "Draft"
	        elif record.date < today:
	            status_value = "Completed"
	        elif record.date == today:
	            status_value = "Today"
	        else:
	            status_value = "Scheduled"
        
	        records_data.append({
	            'id': record.id,
	            'patient_id': record.patient.patient_id if record.patient else None,
	            'patient_name': patient_name_value,
	            'doctor_name': doctor_name_value,
	            'record_type': record.record_type,
	            'record_type_display': record.get_record_type_display(),
	            'title': record.title,
	            'date': record.date.isoformat() if record.date else None,
	            'status': status_value,
	            'created_date': record.created_at.strftime('%Y-%m-%d %H:%M:%S') if record.created_at else None,
	            'last_updated': record.updated_at.strftime('%Y-%m-%d %H:%M:%S') if record.updated_at else None,
	            'created_by_name': record.created_by.full_name if record.created_by else None,
	            'created_by_role': record.created_by.get_role_display() if record.created_by else None,
	            'notes': record.notes
	        })
    
	    # Calculate total pages
	    total_pages = (total_count + page_size - 1) // page_size if page_size > 0 else 1
    
	    return Response({
	        'count': total_count,
	        'page': page,
	        'page_size': page_size,
	        'total_pages': total_pages,
	        'records': records_data,
	        'filters_applied': {
	            'record_type': record_type,
	            'patient_id': patient_id,
	            'patient_name': patient_name,
	            'doctor_name': doctor_name,
	            'status': status_filter,
	            'date_range': {'from': date_from, 'to': date_to},
	            'created_range': {'from': created_from, 'to': created_to},
	            'search': search_term,
	            'ordering': ordering
	        }
	    })


	@action(detail=False, methods=['get'], url_path='all-records/summary')
	def all_records_summary(self, request):
	    """
	    Get a summary of all records without pagination (for dashboard/charts)
	    Returns counts by record type and status
	    """
	    from datetime import date, timedelta
	    from django.db.models import Count
    
	    qs = EMRRecord.objects.select_related('patient').all()
    
	    # Apply role-based filtering
	    if request.user.role != 'ADM':
	        qs = qs.filter(created_by=request.user)
    
	    # Apply filters if provided
	    record_type = request.query_params.get('record_type')
	    if record_type:
	        qs = qs.filter(record_type=record_type)
    
	    patient_id = request.query_params.get('patient_id')
	    if patient_id:
	        qs = qs.filter(patient__patient_id__icontains=patient_id)
    
	    date_from = request.query_params.get('date_from')
	    if date_from:
	        qs = qs.filter(date__gte=date_from)
    
	    date_to = request.query_params.get('date_to')
	    if date_to:
	        qs = qs.filter(date__lte=date_to)
    
	    # Calculate summary statistics
	    today = date.today()
	    last_week = today - timedelta(days=7)
	    last_month = today - timedelta(days=30)
    
	    summary = {
	        'total_records': qs.count(),
	        'total_patients': qs.values('patient').distinct().count(),
	        'by_record_type': list(qs.values('record_type').annotate(
	            count=Count('id'),
	            display_name=F('record_type')
	        ).order_by('-count')),
	        'by_status': {
	            'completed': qs.filter(date__lt=today).count(),
	            'today': qs.filter(date=today).count(),
	            'scheduled': qs.filter(date__gt=today).count(),
	            'draft': qs.filter(date__isnull=True).count()
	        },
	        'by_week': {
	            'last_7_days': qs.filter(created_at__date__gte=last_week).count(),
	            'last_30_days': qs.filter(created_at__date__gte=last_month).count()
	        }
	    }
    
	    return Response(summary)


	@action(detail=False, methods=['get'], url_path='all-records/export')
	def export_all_records(self, request):
	    """
	    Export all records as CSV file
	    """
	    import csv
	    from django.http import HttpResponse
	    from datetime import date
    
	    # Get all records without pagination
	    qs = EMRRecord.objects.select_related(
	        'patient', 'created_by', 'patient__user'
	    ).all()
    
	    # Apply role-based filtering
	    if request.user.role != 'ADM':
	        qs = qs.filter(created_by=request.user)
    
	    # Apply filters if provided (reuse filter logic from all_records)
	    record_type = request.query_params.get('record_type')
	    if record_type:
	        qs = qs.filter(record_type=record_type)
    
	    patient_id = request.query_params.get('patient_id')
	    if patient_id:
	        qs = qs.filter(patient__patient_id__icontains=patient_id)
    
	    # Create CSV response
	    response = HttpResponse(content_type='text/csv')
	    response['Content-Disposition'] = 'attachment; filename="emr_records_export.csv"'
    
	    writer = csv.writer(response)
	    writer.writerow([
	        'Record ID', 'Patient ID', 'Patient Name', 'Doctor', 
	        'Record Type', 'Title', 'Record Date', 'Status', 
	        'Created Date', 'Last Updated', 'Created By', 'Created By Role', 'Notes'
	    ])
    
	    today = date.today()
	    for record in qs:
	        # Get patient name
	        patient_name = "N/A"
	        if record.patient and hasattr(record.patient, 'user') and record.patient.user:
	            patient_name = record.patient.user.full_name or f"{record.patient.user.first_name} {record.patient.user.last_name}".strip()
        
	        # Get doctor name
	        doctor_name = "Not Assigned"
	        if hasattr(record, 'consultation') and record.consultation:
	            if hasattr(record.consultation, 'doctor') and record.consultation.doctor:
	                doctor_name = record.consultation.doctor.full_name or str(record.consultation.doctor)
        
	        # Get status
	        if not record.date:
	            status = "Draft"
	        elif record.date < today:
	            status = "Completed"
	        elif record.date == today:
	            status = "Today"
	        else:
	            status = "Scheduled"
        
	        writer.writerow([
	            record.id,
	            record.patient.patient_id if record.patient else '',
	            patient_name,
	            doctor_name,
	            record.get_record_type_display(),
	            record.title,
	            record.date.isoformat() if record.date else '',
	            status,
	            record.created_at.strftime('%Y-%m-%d %H:%M:%S') if record.created_at else '',
	            record.updated_at.strftime('%Y-%m-%d %H:%M:%S') if record.updated_at else '',
	            record.created_by.full_name if record.created_by else '',
	            record.created_by.get_role_display() if record.created_by else '',
	            record.notes or ''
	        ])
    
	    return response