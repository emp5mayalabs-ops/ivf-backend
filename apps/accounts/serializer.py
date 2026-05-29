from rest_framework import serializers
from .models import User,ClinicalCounsellorProfile,FinancialCounsellorProfile, EmbryologistProfile,AnesthesiologistProfile,NurseProfile,ReceptionistProfile, AdminProfile
from adv_reproduction.models import ReproductiveEndocrinologistProfile
from pharmacy.models import PharmacistProfile
from lab.models import LabTechnicianProfile,AndrologyLabTechnician
from hr.models import  HRManagerProfile
from gynaecology.models import GynaecologistProfile
from adv_reproduction.models import ReproductiveEndocrinologistProfile
from departments.views import auto_assign_primary
from departments.models import Department,StaffDepartmentAssignment

# from patients.models import PatientProfile
# from donor.models import DonorProfile

class LoginSerializer(serializers.Serializer):
    email=serializers.EmailField()
    password=serializers.CharField(write_only=True)

#nested profile serializers

class ReceptionistProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model= ReceptionistProfile
        fields=[
            'employee_id','desk_location','contact_number','can_register_patient','can_access_billing','can_modify_patient_records','can_schedule_appointment','is_department_head'
        ]
        read_only_fields=['employee_id']

class ClinicalCounsellorProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model=ClinicalCounsellorProfile
        fields=['employee_id','is_department_head']
        read_only_fields=['employee_id']


class FinancialCounsellorProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model=FinancialCounsellorProfile
        fields=['employee_id','can_approve_discounts','can_override_insurance','is_department_head']
        read_only_fields=['employee_id']


class ReproductiveEndocrinologistProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model=ReproductiveEndocrinologistProfile
        fields=['employee_id','can_perform_egg_retrieval','can_perform_embryo_transfer','can_design_ivf_protocols','is_department_head']
        read_only_fields=['employee_id']


class GynaecologistProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model=GynaecologistProfile
        fields=['employee_id','can_perform_egg_retrieval','can_assist_ivf','is_department_head']
        read_only_fields=['employee_id']


class AnesthesiologistProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model=AnesthesiologistProfile
        fields=['employee_id','can_edit_anesthesia_records','is_department_head']
        read_only_fields=['employee_id']


class EmbryologistProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model=EmbryologistProfile
        fields=['employee_id','can_perform_icsi','is_department_head']
        read_only_fields=['employee_id']


class NurseProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model=NurseProfile
        fields=['employee_id','is_head_nurse','is_department_head']
        read_only_fields=['employee_id']


class PharmacistProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model=PharmacistProfile
        fields=['employee_id','can_manage_inventory','is_department_head']
        read_only_fields=['employee_id']


class LabTechnicianProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model=LabTechnicianProfile
        fields=['employee_id','is_department_head']
        read_only_fields=['employee_id']


class AndrologyLabTechnicianSerializer(serializers.ModelSerializer):
    class Meta:
        model=AndrologyLabTechnician
        fields=['employee_id','can_perform_dna_frag','can_perform_cryo','is_department_head']
        read_only_fields=['employee_id']


class HRManagerProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model=HRManagerProfile
        fields=['employee_id','can_approve_leaves','can_view_salaries','can_terminate_staff','can_edit_attendance','can_generate_payslips','can_update_documents','is_department_head']
        read_only_fields=['employee_id']


class AdminUserCreateSerializer(serializers.ModelSerializer):
    secondary_department_id=serializers.IntegerField(write_only=True,required=False,allow_null=True)
    department_info=serializers.SerializerMethodField(read_only=True)
    employee_id = serializers.SerializerMethodField(read_only=True)
    #nested profile fields
    receptionist_profile=ReceptionistProfileSerializer(read_only=True)
    clinical_counsellor_profile=ClinicalCounsellorProfileSerializer(read_only=True)
    financial_counsellor_profile=FinancialCounsellorProfileSerializer(read_only=True)
    endocrinologist_profile=ReproductiveEndocrinologistProfileSerializer(read_only=True)
    gynaec_profile=GynaecologistProfileSerializer(read_only=True)
    anesth_profile=AnesthesiologistProfileSerializer(read_only=True)
    embryologist_profile=EmbryologistProfileSerializer(read_only=True)
    nurse_profile=NurseProfileSerializer(read_only=True)
    pharmacist_profile=PharmacistProfileSerializer(read_only=True)
    technician_profile=LabTechnicianProfileSerializer(read_only=True)
    andrology_technician_profile=AndrologyLabTechnicianSerializer(read_only=True)
    hr_profile=HRManagerProfileSerializer(read_only=True)

    class Meta:
        model=User
        fields = ['id','email','full_name','role','password','is_active','date_joined','secondary_department_id','department_info','employee_id',
        #nested_profiles
        'receptionist_profile','clinical_counsellor_profile','financial_counsellor_profile','endocrinologist_profile','gynaec_profile','anesth_profile','embryologist_profile','nurse_profile','pharmacist_profile','technician_profile','andrology_technician_profile','hr_profile',
        ]
        extra_kwargs={'password':{'write_only':True}}
    def get_department_info(self,obj):
        assignments=obj.staff_assignments.filter(is_active=True).select_related('department')
        return[
            {
                'id': a.department.id,
                'name': a.department.name,
                'code': a.department.code,
                'role_in_dept': a.role_in_dept,
            }
            for a in assignments
        ]

    def get_employee_id(self, obj):
        profile_map = {
            'REC': 'receptionist_profile',
            'CCO': 'clinical_counsellor_profile',
            'FCO': 'financial_counsellor_profile',
            'END': 'endocrinologist_profile',
            'GYN': 'gynaec_profile',
            'ANE': 'anesth_profile',
            'EMB': 'embryologist_profile',
            'NUR': 'nurse_profile',
            'AND': 'andrology_technician_profile',
            'TEC': 'technician_profile',
            'PHA': 'pharmacist_profile',
            'HRM': 'hr_profile',
        }
        profile_attr = profile_map.get(obj.role)
        if profile_attr:
            profile = getattr(obj, profile_attr, None)
            if profile:
                return profile.employee_id
        return None

    def create(self, validated_data):
        secondary_department_id=validated_data.pop('secondary_department_id',None)
        password = validated_data.pop('password')
        user = User.objects.create_user(password=password, **validated_data)
        auto_assign_primary(user)
        if secondary_department_id:
            try:
                dept=Department.objects.get(id=secondary_department_id)
                StaffDepartmentAssignment.objects.get_or_create(
                    user=user,
                    department=dept,
                    defaults={'role_in_dept':'SECONDARY',
                              'unit': validated_data.get('secondary_unit','')},
                )
            except Exception:
                pass

        profile_map = {
            'REC': ReceptionistProfile,
            'CCO': ClinicalCounsellorProfile,
            'FCO': FinancialCounsellorProfile,
            'END': ReproductiveEndocrinologistProfile,
            'GYN': GynaecologistProfile,
            'ANE': AnesthesiologistProfile,
            'EMB': EmbryologistProfile,
            'NUR': NurseProfile,
            'AND': AndrologyLabTechnician,
            'TEC': LabTechnicianProfile,
            'PHA': PharmacistProfile,
            'HRM': HRManagerProfile,
            'ADM': AdminProfile,
        }

        profile_model = profile_map.get(user.role)
        if profile_model:
            profile_model.objects.create(user=user)
        return user    

        # if user.role =='REC':
        #     ReceptionistProfile.objects.create(user=user)
        # elif user.role =='CCO':
        #     ClinicalCounsellorProfile.objects.create(user=user)
        # elif user.role =='FCO':
        #     FinancialCounsellorProfile.objects.create(user=user)
        # elif user.role =='END':
        #     ReproductiveEndocrinologistProfile.objects.create(user=user)
        # elif user.role =='GYN':
        #     GynaecologistProfile.objects.create(user=user)
        # elif user.role =='EMB':
        #     EmbryologistProfile.objects.create(user=user)
        # elif user.role =='ANE':
        #     AnesthesiologistProfile.objects.create(user=user)
        # elif user.role =='NUR':
        #     NurseProfile.objects.create(user=user)
        # elif user.role =='PHA':
        #     PharmacistProfile.objects.create(user=user)
        # elif user.role =='TEC':
        #     LabTechnicianProfile.objects.create(user=user)
        # elif user.role =='AND':
        #     AndrologyLabTechnician.objects.create(user=user)
        # # elif user.role =='PAT':
        # #     PatientProfile.objects.create(user=user)
        # elif user.role == 'HRM':
        #     HRManagerProfile.objects.create(user=user)
        # elif user.role=='ADM':
        #     AdminProfile.objects.create(user=user)

        # return user 