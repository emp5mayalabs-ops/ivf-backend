from rest_framework import serializers
from .models import OPTicket
from patients.models import PatientProfile
from accounts.models import User

class OPTicketSerializer(serializers.ModelSerializer):
	patient_name=serializers.SerializerMethodField()
	patient_id_str=serializers.SerializerMethodField()
	doctor_name=serializers.SerializerMethodField()
	doctor_role=serializers.SerializerMethodField()
	department_name=serializers.SerializerMethodField()
	created_by_name=serializers.SerializerMethodField()
	visit_reason_display=serializers.CharField(source='get_visit_reason_display',read_only=True)
	status_display=serializers.CharField(source='get_status_display',read_only=True)
	class Meta:
		model=OPTicket
		fields=[
	    	'id','token_number','date','patient','patient_name','patient_id_str','assigned_doctor','doctor_name','doctor_role','department','department_name','visit_reason','visit_reason_display','chief_complaint','status','status_display','created_by','created_by_name','created_at','updated_at',
		]
		read_only_fields=['id','token_number','date','created_at','updated_at','created_by']
	
	def get_patient_name(self,obj):
	    return obj.patient.user.full_name if obj.patient else None
	
	def get_patient_id_str(self,obj):
		return obj.patient.patient_id if obj.patient else None
	
	def get_doctor_name(self,obj):
		return obj.assigned_doctor.full_name if obj.assigned_doctor else None
	
	def get_doctor_role(self,obj):
		return obj.assigned_doctor.get_role_display() if obj.assigned_doctor else None
	
	def get_department_name(self,obj):
	    return obj.department_name if obj.department else None
	
	def get_created_by_name(self,obj):
		return obj.created_by.full_name if obj.created_by else None
	
	def create(self,validated_data):
		validated_data['token_number']=OPTicket.next_token_for_today()
		validated_data['created_by']=self.context['request'].user
		return super().create(validated_data)

class PatientBasicSerializer(serializers.ModelSerializer):
	full_name=serializers.CharField(source='user.full_name',read_only=True)
	email=serializers.CharField(source='user.email',read_only=True)
	is_active=serializers.BooleanField(source='user.is_active',read_only=True)
	
	class Meta:
		model=PatientProfile
		fields=['id','patient_id','full_name','email','is_active','phone','date_of_birth','gender','blood_group','address','emergency_contact_name','emergency_contact_phone','treatment_type','status','assigned_doctor','registered_on','notes']
		read_only_fields=['id','patient_id','registered_on']
	
	def to_representation(self, instance):
		rep=super().to_representation(instance)
		if instance.assigned_doctor:
			rep['assigned_doctor_name']=instance.assigned_doctor.full_name
		else:
			rep['assigned_doctor_name']=None
		return rep

class DoctorChoiceSerializer(serializers.ModelSerializer):
	role_display=serializers.CharField(source='get_role_display',read_only=True)
	class Meta:
		model=User
		fields=['id','full_name','role','role_display']

