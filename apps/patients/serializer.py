from rest_framework import serializers
from .models import PatientProfile
from accounts.models import User

class PatientUserSerializer(serializers.ModelSerializer):
	class Meta:
		model=User
		fields=['id','email','full_name']

class AssignedDoctorSerializer(serializers.ModelSerializer):
	role_display=serializers.SerializerMethodField()
	class Meta:
		model=User
		fields=['id','full_name','email','role','role_display']
	def get_role_display(self,obj):
		return obj.get_role_display()

class PatientProfileSerializer(serializers.ModelSerializer):
	user=PatientUserSerializer(read_only=True)
	assigned_doctor=AssignedDoctorSerializer(read_only=True)
	assigned_doctor_id=serializers.PrimaryKeyRelatedField(
		queryset=User.objects.filter(role__in=['GYN','REN']),
		source='assigned_doctor',
		write_only=True,
		required=False,
		allow_null=True,
	)
	partner_info =serializers.SerializerMethodField(read_only=True)
	age=serializers.ReadOnlyField()
	status_display=serializers.SerializerMethodField()
	treatment_type_display=serializers.SerializerMethodField()
	gender_display=serializers.SerializerMethodField()

	class Meta:
		model=PatientProfile
		fields=[
			'id','patient_id','slug','user','assigned_doctor','assigned_doctor_id','phone','date_of_birth','age','gender','gender_display','blood_group','address','insurance_policy_number','insurance_details','emergency_contact_name','emergency_contact_phone','treatment_type','treatment_type_display','status','status_display','partner','partner_info','registered_on','updated_on','notes','is_active'
		]
		read_only_fields=['id','patient_id','slug','registered_on','updated_on']
		
	def get_status_display(self,obj):
			return obj.get_status_display()
		
	def get_treatment_type_display(self,obj):
			return obj.get_treatment_type_display() if obj.gender else None
	
	def get_partner_info(self,obj):
		if obj.partner:
			return {
				'id': obj.partner.id,
				'patient_id':obj.partner.patient_id,
				'full_name':obj.partner.user.full_name,
				'email':obj.partner.user.email,
			}
		return None
	def get_gender_display(self, obj):
		return obj.get_gender_display() if obj.gender else None
	

class PatientCreateSerializer(serializers.Serializer):
	#User + Patientprofile
	full_name=serializers.CharField()
	email=serializers.EmailField()
	password=serializers.CharField(write_only=True)

	#profile fields
	phone =serializers.CharField(required=False, allow_blank=True)
	date_of_birth=serializers.DateField(required=False,allow_null=True)
	gender=serializers.ChoiceField(choices=['M','F','O'],required=False,allow_blank=True)
	blood_group=serializers.CharField(required=False, allow_blank=True)
	address = serializers.CharField(required=False, allow_blank=True)
	insurance_policy_number=serializers.CharField(required=False, allow_blank=True)
	insurance_details=serializers.CharField(required=False, allow_blank=True)
	emergency_contact_name=serializers.CharField(required=False, allow_blank=True)
	emergency_contact_phone=serializers.CharField(required=False, allow_blank=True)
	treatment_type=serializers.ChoiceField(choices=PatientProfile._meta.get_field('treatment_type').choices, required=False,allow_blank=True,)
	status = serializers.ChoiceField(PatientProfile._meta.get_field('status').choices,default='PEN',)
	assigned_doctor_id=serializers.PrimaryKeyRelatedField(
		queryset=User.objects.filter(role__in=['GYN','REN']),
		required=False, allow_null=True,
	)
	notes = serializers.CharField(required=False,allow_blank=True)

	def validate_email(self,value):
		if User.objects.filter(email=value).exists():
			raise serializers.ValidationError("A user with this email already exists.")
		return value
	def create(self,validated_data):
		from departments.views import auto_assign_primary

		#Extract user fields
		full_name=validated_data.pop('full_name')
		email=validated_data.pop('email')
		password=validated_data.pop('password')
		doctor=validated_data.pop('assigned_doctor_id',None)

		#Create user
		user=User.objects.create_user(
			email=email,
			password=password,
			full_name=full_name,
			role='PAT',
		)

		profile=PatientProfile.objects.create(
			user=user,
			assigned_doctor=doctor,
			**validated_data,
		)
		auto_assign_primary(user)
		return profile
