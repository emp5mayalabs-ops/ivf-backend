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
	EMRRecordListSerializer,EMRRecordDetailSerializer,EMRRecordCreateSerializer,ConsultationNoteSerializer,DiagnosisSerializer,PrescriptionSerializer,LabResultSerializer,ScanReportSerializer,ProcedureNoteSerializer,TreatmentCycleSerializer,NursingNoteSerializer,PharmacyNoteSerializer,AndrologyNoteSerializer,CounsellingNoteSerializer,MedicalHistoryDocumentSerializer
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