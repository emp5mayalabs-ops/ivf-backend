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
		
		recent_qs = PatientProfile.objects.select_related('user').order_by('-updated_on')[:5]
		recent_patients = []
		for p in recent_qs:
			recent_patients.append({
				"id": p.id,
				"patient_id": p.patient_id,
				"full_name": p.user.full_name if p.user else "",
				"last_viewed": p.updated_on.isoformat() if p.updated_on else None
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
