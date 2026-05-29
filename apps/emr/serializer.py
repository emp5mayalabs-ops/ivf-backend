from rest_framework import serializers
from .models import EMRRecord,ROLE_ALLOWED_RECORD_TYPES,ConsultationNote,Diagnosis,Prescription,LabResult,ScanReport,ProcedureNote,TreatmentCycle,NursingNote,PharmacyNote,AndrologyNote,CounsellingNote,MedicalHistoryDocument


#SUB-SECTIONS

class ConsultationNoteSerializer(serializers.ModelSerializer):
	class Meta:
		model=ConsultationNote
		fields=['id','chief_complaint','history','examination','assessment','plan']

class DiagnosisSerializer(serializers.ModelSerializer):
	class Meta:
		model=Diagnosis
		fields=['id','icd_code','description','is_primary']

class PrescriptionSerializer(serializers.ModelSerializer):
	class Meta:
		model=Prescription
		fields=['id','medication_name','dosage','frequency','duration','route','instructions']
	
class LabResultSerializer(serializers.ModelSerializer):
	class Meta:
		model=LabResult
		fields=['id','test_name','result_value','unit','reference_range','is_abnormal','notes','report_file','report_image']

class ScanReportSerializer(serializers.ModelSerializer):
	class Meta:
		model=ScanReport
		fields=['id','scan_type','findings','follicle_count','endometrium','impression','image','report_file']

class ProcedureNoteSerializer(serializers.ModelSerializer):
	class Meta:
		model=ProcedureNote
		fields=['id','procedure_name','performed_by','details','outcome','complications']
	def get_performed_by_name(self,obj):
		return obj.performed_by.full_name if obj.performed_by else None

class TreatmentCycleSerializer(serializers.ModelSerializer):
	class Meta:
		model=TreatmentCycle
		fields=['id','cycle_type','cycle_number','start_date','end_date','status','eggs_retrieved','eggs_fertilized','embryos_formed','embryos_transfered','embryos_frozen','outcome','notes']

class NursingNoteSerializer(serializers.ModelSerializer):
	class Meta:
		model=NursingNote
		fields=['id','vital_bp','vital_pulse','vital_temp','vital_spo2','vital_weight','observations','medications_given','instructions_given']

class PharmacyNoteSerializer(serializers.ModelSerializer):
	class Meta:
		model=PharmacyNote
		fields=['dispensed_items','batch_numbers','dispensing_notes','counselling_given']

class AndrologyNoteSerializer(serializers.ModelSerializer):
	class Meta:
		model=AndrologyNote
		fields=['id','sample_type','volume_ml','concentration','motility_percent','morphology_percent','dna_fragmentation','who_criteria','impression','notes','report_file','report_image']

class CounsellingNoteSerializer(serializers.ModelSerializer):
	class Meta:
		model=CounsellingNote
		fields=['id','session_type','concerns_raised','advice_given','follow_up_required','follow_up_date','notes']

#EMR Record Serializer (lightweight)

class EMRRecordListSerializer(serializers.ModelSerializer):
	created_by_name=serializers.SerializerMethodField()
	created_by_role=serializers.SerializerMethodField()
	record_type_display=serializers.CharField(source='get_record_type_display',read_only=True)
	class Meta:
		model=EMRRecord
		fields=['id','record_type','record_type_display','title','date','notes','created_by','created_by_name','created_by_role','created_at'] 
	
	def get_created_by_name(self,obj):
		return obj.created_by.full_name if obj.created_by else None
	def get_created_by_role(self,obj):
		return obj.created_by.get_role_display() if obj.created_by else None

#EMRRecord detail -with all subsections
class EMRRecordDetailSerializer(serializers.ModelSerializer):
	created_by_name=serializers.SerializerMethodField()
	created_by_role=serializers.SerializerMethodField()
	record_type_display=serializers.CharField(source="get_record_type_display",read_only=True)

	#All sub-sections
	consultation = ConsultationNoteSerializer(read_only=True)
	diagnosis=DiagnosisSerializer(many=True, read_only=True)
	prescriptions=PrescriptionSerializer(many=True, read_only=True)
	lab_results=LabResultSerializer(many=True, read_only=True)
	scans=ScanReportSerializer(many=True,read_only=True)
	procedures=ProcedureNoteSerializer(many=True,read_only=True)
	cycle=TreatmentCycleSerializer(read_only=True)
	nursing_note=NursingNoteSerializer(read_only=True)
	pharmacy_note=PharmacyNoteSerializer(read_only=True)
	andrology_note=AndrologyNoteSerializer(read_only=True)
	counselling_note=CounsellingNoteSerializer(read_only=True)

	class Meta:
		model=EMRRecord
		fields=['id','record_type','record_type_display','title','date','notes','created_by','created_by_name','created_by_role','created_at','updated_at','consultation','diagnosis','prescriptions','lab_results','scans','procedures','cycle','nursing_note','pharmacy_note','andrology_note','counselling_note',]

	def get_created_by_name(self,obj):
		return obj.created_by.full_name if obj.created_by else None

	def get_created_by_role(self,obj):
		return obj.created_by.get_role_display() if obj.created_by else None

#EMR Record Create
class EMRRecordCreateSerializer(serializers.ModelSerializer):
	#Sub-section data
	consultation_data=ConsultationNoteSerializer(write_only=True, required=False)
	diagnosis_data=DiagnosisSerializer(write_only=True,required=False, many=True)
	prescription_data=PrescriptionSerializer(write_only=True,required=False, many=True)
	lab_result_data=LabResultSerializer(write_only=True,required=False, many=True)
	scan_data=ScanReportSerializer(write_only=True,required=False, many=True)
	procedure_data=ProcedureNoteSerializer(write_only=True,required=False,many=True)
	cycle_data=TreatmentCycleSerializer(write_only=True,required=False)
	nursing_note_data=NursingNoteSerializer(write_only=True,required=False)
	pharmacy_note_data=PharmacyNoteSerializer(write_only=True,required=False)
	andrology_note_data=AndrologyNoteSerializer(write_only=True,required=False)
	counselling_note_data=CounsellingNoteSerializer(write_only=True,required=False)
	
	class Meta:
		model=EMRRecord
		fields=['id','patient','record_type','title','date','notes','consultation_data','diagnosis_data','prescription_data','lab_result_data','scan_data','procedure_data','cycle_data','nursing_note_data','pharmacy_note_data','andrology_note_data','counselling_note_data']
		read_only_fields=['id']

	def validate_record_type(self,value):
		request=self.context.get('request')
		if request and hasattr(request,'user'):
			allowed=ROLE_ALLOWED_RECORD_TYPES.get(request.user.role, [])
			if value not in allowed:
				raise serializers.ValidationError(f"Your role ({request.user.get_role_display()}) is not allowed to create records of type '{value}'")
			return value
	
	def create(self,validated_data):
		#pop all sub-section data
		consultation_data=validated_data.pop('consultation_data',None)
		diagnosis_data=validated_data.pop('diagnosis_data',[])
		prescription_data=validated_data.pop('prescription_data',[])
		lab_result_data=validated_data.pop('lab_result_data',[])
		scan_data=validated_data.pop('scan_data',[])
		procedure_data=validated_data.pop('procedure_data',[])
		cycle_data=validated_data.pop('cycle_data',None)
		nursing_note_data=validated_data.pop('nursing_note_data',None)
		pharmacy_note_data=validated_data.pop('pharmacy_note_data',None)
		andrology_note_data=validated_data.pop('andrology_note_data',None)
		counselling_note_data=validated_data.pop('counselling_note_data',None)

		#Set created_by from request
		request=self.context.get('request')
		validated_data['created_by'] = request.user if request else None

		record=EMRRecord.objects.create(**validated_data)

		#Create sub-sections
		if consultation_data:
			ConsultationNote.objects.create(record=record, **consultation_data)
		for d in diagnosis_data:
			Diagnosis.objects.create(record=record, **d)
		for p in prescription_data:
			Prescription.objects.create(record=record, **p)
		for l in lab_result_data:
			LabResult.objects.create(record=record, **l)
		for s in scan_data:
			ScanReport.objects.create(record=record, **s)
		for p in procedure_data:
			ProcedureNote.objects.create(record=record, **p)
		if cycle_data:
			TreatmentCycle.objects.create(record=record, **cycle_data)
		if nursing_note_data:
			NursingNote.objects.create(record=record, **nursing_note_data)
		if pharmacy_note_data:
			PharmacyNote.objects.create(record=record, **pharmacy_note_data)
		if andrology_note_data:
			AndrologyNote.objects.create(record=record, **andrology_note_data)
		if counselling_note_data:
			CounsellingNote.objects.create(record=record, **counselling_note_data)

		return record

#Medical History Document

class MedicalHistoryDocumentSerializer(serializers.ModelSerializer):
	uploaded_by_name = serializers.SerializerMethodField()
	uploaded_by_role = serializers.SerializerMethodField()
	document_type_display = serializers.CharField(source='get_document_type_display',read_only=True)

	class Meta:
		model=MedicalHistoryDocument
		fields=['id','patient','document_type','document_type_display','title','file','notes','document_date','uploaded_at','uploaded_by','uploaded_by_name','uploaded_by_role']
		read_only_fields= ['id','uploaded_at','uploaded_by']
	
	def get_uploaded_by_name(self,obj):
		return obj.uploaded_by.full_name if obj.uploaded_by else None
	def get_uploaded_by_role(self,obj):
		return obj.uploaded_by.get_role_display() if obj.uploaded_by else None
	
	def create(self,validated_data):
		request=self.context.get('request')
		validated_data['uploaded_by'] = request.user if request else None
		return super().create(validated_data)

class EMRRecordUpdateSerializer(serializers.ModelSerializer):
	class Meta:
		model=EMRRecord
		fields=['title','date','notes']
	def validate_record_type(self,value):
		raise serializers.ValidationError("Record type cannot be changed after creation")