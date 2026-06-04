from rest_framework import serializers
from django.utils import timezone
from .models import OPTicket, Appointment
from patients.models import PatientProfile
from accounts.models import User
from .utils import generate_ticket_qr_code


class OPTicketSerializer(serializers.ModelSerializer):
    date = serializers.DateField(read_only=True)
    patient_name = serializers.SerializerMethodField()
    patient_id_str = serializers.SerializerMethodField()
    doctor_name = serializers.SerializerMethodField()
    doctor_role = serializers.SerializerMethodField()
    department_name = serializers.SerializerMethodField()
    created_by_name = serializers.SerializerMethodField()
    visit_reason_display = serializers.CharField(source='get_visit_reason_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    qr_code = serializers.SerializerMethodField()
    
    class Meta:
        model = OPTicket
        fields = [
            'id', 'token_number', 'date', 'patient', 'patient_name', 'patient_id_str',
            'assigned_doctor', 'doctor_name', 'doctor_role', 'department', 'department_name',
            'visit_reason', 'visit_reason_display', 'notes', 'payment_done', 'status',
            'status_display', 'created_by', 'created_by_name', 'created_at', 'updated_at',
            'qr_code'
        ]
        read_only_fields = ['id', 'token_number', 'date', 'created_at', 'updated_at', 'created_by', 'qr_code']
    
    def get_patient_name(self, obj):
        return obj.patient.user.full_name if obj.patient else None
    
    def get_patient_id_str(self, obj):
        return obj.patient.patient_id if obj.patient else None
    
    def get_doctor_name(self, obj):
        return obj.assigned_doctor.full_name if obj.assigned_doctor else None
    
    def get_doctor_role(self, obj):
        return obj.assigned_doctor.get_role_display() if obj.assigned_doctor else None
    
    def get_department_name(self, obj):
        return obj.department.name if obj.department else None
    
    def get_created_by_name(self, obj):
        return obj.created_by.full_name if obj.created_by else None
    
    def get_qr_code(self, obj):
        if obj.status == 'CANCELLED':
            return None
        
        try:
            qr_base64 = generate_ticket_qr_code(obj)
            return qr_base64
        except Exception as e:
            return None
    
    def create(self, validated_data):
        validated_data['token_number'] = OPTicket.next_token_for_today()
        validated_data['created_by'] = self.context['request'].user
        return super().create(validated_data)


class PatientBasicSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(source='user.full_name', read_only=True)
    email = serializers.CharField(source='user.email', read_only=True)
    is_active = serializers.BooleanField(source='user.is_active', read_only=True)
    
    class Meta:
        model = PatientProfile
        fields = ['id', 'patient_id', 'full_name', 'email', 'is_active', 'phone', 'date_of_birth', 
                  'gender', 'blood_group', 'address', 'emergency_contact_name', 'emergency_contact_phone', 
                  'treatment_type', 'status', 'assigned_doctor', 'registered_on', 'notes']
        read_only_fields = ['id', 'patient_id', 'registered_on']
    
    def to_representation(self, instance):
        rep = super().to_representation(instance)
        if instance.assigned_doctor:
            rep['assigned_doctor_name'] = instance.assigned_doctor.full_name
        else:
            rep['assigned_doctor_name'] = None
        return rep


class DoctorChoiceSerializer(serializers.ModelSerializer):
    role_display = serializers.CharField(source='get_role_display', read_only=True)
    
    class Meta:
        model = User
        fields = ['id', 'full_name', 'role', 'role_display']


# ========== APPOINTMENT SERIALIZER ==========
class AppointmentSerializer(serializers.ModelSerializer):
    patient_name = serializers.SerializerMethodField()
    patient_mrn = serializers.SerializerMethodField()
    patient_phone = serializers.SerializerMethodField()
    patient_email = serializers.SerializerMethodField()
    patient_age = serializers.SerializerMethodField()
    
    doctor_name = serializers.SerializerMethodField()
    doctor_specialization = serializers.SerializerMethodField()
    doctor_room = serializers.SerializerMethodField()
    
    department_name = serializers.SerializerMethodField()
    created_by_name = serializers.SerializerMethodField()
    
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    appointment_type_display = serializers.CharField(source='get_appointment_type_display', read_only=True)
    visit_reason_display = serializers.CharField(source='get_visit_reason_display', read_only=True)
    
    qr_code_base64 = serializers.SerializerMethodField()
    
    # Write-only fields for creating appointments
    patient_id = serializers.IntegerField(write_only=True, required=True)
    doctor_id = serializers.IntegerField(write_only=True, required=True)
    department_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    
    # Read-only fields for response
    patient = serializers.PrimaryKeyRelatedField(read_only=True)
    doctor = serializers.PrimaryKeyRelatedField(read_only=True)
    department = serializers.PrimaryKeyRelatedField(read_only=True)
    
    class Meta:
        model = Appointment
        fields = [
            'id', 'appointment_id', 'token_number',
            'patient', 'patient_id', 'patient_name', 'patient_mrn', 'patient_phone', 
            'patient_email', 'patient_age',
            'doctor', 'doctor_id', 'doctor_name', 'doctor_specialization', 'doctor_room',
            'department', 'department_id', 'department_name',
            'appointment_date', 'appointment_time', 'time_slot', 'duration_minutes',
            'appointment_type', 'appointment_type_display',
            'status', 'status_display',
            'visit_reason', 'visit_reason_display', 'symptoms', 'notes',
            'payment_status', 'payment_amount',
            'cancelled_at', 'cancellation_reason',
            'rescheduled_from', 'rescheduled_count',
            'created_by', 'created_by_name',
            'created_at', 'updated_at',
            'qr_code_base64',
            'reminder_sent', 'reminder_sent_at', 'reminder_type'
        ]
        read_only_fields = [
            'id', 'appointment_id', 'token_number', 'created_at', 'updated_at', 
            'qr_code_base64', 'cancelled_at', 'rescheduled_count'
        ]
    
    def get_patient_name(self, obj):
        return obj.patient.user.full_name if obj.patient else None
    
    def get_patient_mrn(self, obj):
        return obj.patient.patient_id if obj.patient else None
    
    def get_patient_phone(self, obj):
        return obj.patient.phone if obj.patient else None
    
    def get_patient_email(self, obj):
        return obj.patient.user.email if obj.patient else None
    
    def get_patient_age(self, obj):
        if obj.patient and obj.patient.date_of_birth:
            today = timezone.now().date()
            age = today.year - obj.patient.date_of_birth.year
            if today.month < obj.patient.date_of_birth.month or \
               (today.month == obj.patient.date_of_birth.month and today.day < obj.patient.date_of_birth.day):
                age -= 1
            return age
        return None
    
    def get_doctor_name(self, obj):
        return obj.doctor.full_name if obj.doctor else None
    
    def get_doctor_specialization(self, obj):
        return obj.doctor.get_role_display() if obj.doctor else None
    
    def get_doctor_room(self, obj):
        return getattr(obj.doctor, 'room_number', 'Not assigned') if obj.doctor else None
    
    def get_department_name(self, obj):
        return obj.department.name if obj.department else None
    
    def get_created_by_name(self, obj):
        return obj.created_by.full_name if obj.created_by else None
    
    def get_qr_code_base64(self, obj):
        if obj.qr_code:
            return f"data:image/png;base64,{obj.qr_code}"
        return None
    
    def validate_appointment_date(self, value):
        if value < timezone.now().date():
            raise serializers.ValidationError("Appointment date cannot be in the past")
        return value
    
    def validate_time_slot(self, value):
        if value:
            valid_slots = [
                '09:00 AM', '09:30 AM', '10:00 AM', '10:30 AM',
                '11:00 AM', '11:30 AM', '12:00 PM', '12:30 PM',
                '02:00 PM', '02:30 PM', '03:00 PM', '03:30 PM',
                '04:00 PM', '04:30 PM'
            ]
            if value not in valid_slots:
                raise serializers.ValidationError(f"Invalid time slot. Must be one of: {', '.join(valid_slots)}")
        return value
    
    def validate(self, data):
        """Cross-field validation"""
        # Create a mutable copy
        validated_data = data.copy()
        
        # Get patient from patient_id
        patient_id = validated_data.get('patient_id')
        if not patient_id:
            raise serializers.ValidationError({'patient_id': 'patient_id is required'})
        
        try:
            patient = PatientProfile.objects.get(id=patient_id)
            validated_data['patient'] = patient
        except PatientProfile.DoesNotExist:
            raise serializers.ValidationError({'patient_id': f'Patient with id {patient_id} not found'})
        
        # Get doctor from doctor_id
        doctor_id = validated_data.get('doctor_id')
        if not doctor_id:
            raise serializers.ValidationError({'doctor_id': 'doctor_id is required'})
        
        try:
            doctor = User.objects.get(id=doctor_id, role__in=['END', 'GYN', 'ANE'])
            validated_data['doctor'] = doctor
        except User.DoesNotExist:
            raise serializers.ValidationError({'doctor_id': f'Doctor with id {doctor_id} not found'})
        
        # Get department from department_id (optional)
        department_id = validated_data.get('department_id')
        if department_id:
            try:
                from departments.models import Department
                department = Department.objects.get(id=department_id)
                validated_data['department'] = department
            except:
                pass
        
        # Check for duplicate appointment
        appointment_date = validated_data.get('appointment_date')
        
        if patient and appointment_date:
            existing = Appointment.objects.filter(
                patient=patient,
                appointment_date=appointment_date,
                status__in=['SCHEDULED', 'CONFIRMED', 'IN_PROGRESS']
            ).exclude(id=self.instance.id if self.instance else None)
            
            if existing.exists():
                raise serializers.ValidationError(
                    "Patient already has an appointment on this date"
                )
        
        # Check doctor availability for time slot
        time_slot = validated_data.get('time_slot')
        
        if doctor and appointment_date and time_slot:
            available_slots = Appointment.get_available_time_slots(doctor.id, appointment_date)
            if time_slot not in available_slots:
                raise serializers.ValidationError(
                    f"Time slot {time_slot} is not available for this doctor. Available slots: {', '.join(available_slots)}"
                )
        
        return validated_data
    
    def create(self, validated_data):
        # Remove ID fields that were used for lookups
        validated_data.pop('patient_id', None)
        validated_data.pop('doctor_id', None)
        validated_data.pop('department_id', None)
        
        # Set created_by from request
        validated_data['created_by'] = self.context['request'].user
        
        # Create appointment
        appointment = Appointment.objects.create(**validated_data)
        
        # Generate QR code
        appointment.generate_qr_code(self.context.get('request'))
        appointment.save()
        
        return appointment
    
    def update(self, instance, validated_data):
        # Remove ID fields if present
        validated_data.pop('patient_id', None)
        validated_data.pop('doctor_id', None)
        validated_data.pop('department_id', None)
        
        # Update fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        # If appointment date changed, update token
        if 'appointment_date' in validated_data:
            if instance.appointment_date == timezone.now().date():
                last_token = Appointment.objects.filter(
                    appointment_date=instance.appointment_date
                ).order_by('-token_number').first()
                instance.token_number = (last_token.token_number + 1) if last_token else 1
        
        instance.save()
        
        # Regenerate QR code if needed
        if 'appointment_date' in validated_data or 'appointment_time' in validated_data:
            instance.generate_qr_code(self.context.get('request'))
            instance.save()
        
        return instance


# ========== APPOINTMENT LIST SERIALIZER ==========
class AppointmentListSerializer(serializers.ModelSerializer):
    patient_name = serializers.SerializerMethodField()
    patient_mrn = serializers.SerializerMethodField()
    doctor_name = serializers.SerializerMethodField()
    department_name = serializers.SerializerMethodField()
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    time_display = serializers.SerializerMethodField()
    
    class Meta:
        model = Appointment
        fields = [
            'id', 'appointment_id', 'token_number',
            'patient_name', 'patient_mrn',
            'doctor_name', 'department_name',
            'appointment_date', 'time_display', 'time_slot',
            'appointment_type', 'status', 'status_display',
            'visit_reason', 'payment_status'
        ]
    
    def get_patient_name(self, obj):
        return obj.patient.user.full_name if obj.patient else None
    
    def get_patient_mrn(self, obj):
        return obj.patient.patient_id if obj.patient else None
    
    def get_doctor_name(self, obj):
        return obj.doctor.full_name if obj.doctor else None
    
    def get_department_name(self, obj):
        if obj.department:
            return obj.department.name
        if obj.doctor and hasattr(obj.doctor, 'department') and obj.doctor.department:
            return obj.doctor.department.name
        return None
    
    def get_time_display(self, obj):
        if obj.appointment_time:
            return obj.appointment_time.strftime('%I:%M %p')
        return obj.time_slot or 'Not scheduled'


# ========== APPOINTMENT STATUS UPDATE SERIALIZER ==========
class AppointmentStatusUpdateSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=Appointment.APPOINTMENT_STATUS)
    cancellation_reason = serializers.CharField(required=False, allow_blank=True)
    notes = serializers.CharField(required=False, allow_blank=True)
    
    def validate_status(self, value):
        valid_transitions = {
            'SCHEDULED': ['CONFIRMED', 'CANCELLED', 'RESCHEDULED'],
            'CONFIRMED': ['IN_PROGRESS', 'CANCELLED', 'RESCHEDULED'],
            'IN_PROGRESS': ['COMPLETED', 'CANCELLED'],
            'COMPLETED': [],
            'CANCELLED': [],
            'NO_SHOW': [],
            'RESCHEDULED': ['SCHEDULED']
        }
        
        instance = self.context.get('instance')
        if instance and instance.status in valid_transitions:
            if value not in valid_transitions[instance.status]:
                raise serializers.ValidationError(
                    f"Cannot transition from {instance.status} to {value}"
                )
        return value


# ========== APPOINTMENT RESCHEDULE SERIALIZER ==========
class AppointmentRescheduleSerializer(serializers.Serializer):
    new_date = serializers.DateField()
    new_time_slot = serializers.CharField(required=False, allow_blank=True)
    reason = serializers.CharField(required=False, allow_blank=True)
    
    def validate_new_date(self, value):
        if value < timezone.now().date():
            raise serializers.ValidationError("New appointment date cannot be in the past")
        return value
    
    def validate(self, data):
        instance = self.context.get('instance')
        
        if instance and instance.status in ['COMPLETED', 'CANCELLED']:
            raise serializers.ValidationError(
                f"Cannot reschedule a {instance.get_status_display()} appointment"
            )
        
        if instance and instance.doctor:
            available_slots = Appointment.get_available_time_slots(
                instance.doctor.id, 
                data['new_date']
            )
            
            if data.get('new_time_slot') and data['new_time_slot'] not in available_slots:
                raise serializers.ValidationError(
                    f"Time slot {data['new_time_slot']} is not available"
                )
        
        return data