# apps/doctor/serializers.py
from rest_framework import serializers
from django.utils import timezone
from datetime import timedelta

from appointments.models import OPTicket, Appointment
from patients.models import PatientProfile
from accounts.models import User
from emr.models import EMRRecord, ConsultationNote, Prescription


class DoctorQueueSerializer(serializers.ModelSerializer):
    """Serializer for doctor's queue/ticket data"""
    
    patient_name = serializers.SerializerMethodField()
    patient_mrn = serializers.SerializerMethodField()
    patient_phone = serializers.SerializerMethodField()
    patient_age = serializers.SerializerMethodField()
    wait_time = serializers.SerializerMethodField()
    arrival_time = serializers.SerializerMethodField()
    
    class Meta:
        model = OPTicket
        fields = [
            'id', 'token_number', 'patient_name', 'patient_mrn', 
            'patient_phone', 'patient_age', 'status', 'wait_time',
            'arrival_time', 'visit_reason', 'notes', 'created_at'
        ]
    
    def get_patient_name(self, obj):
        return obj.patient.user.full_name if obj.patient and obj.patient.user else ""
    
    def get_patient_mrn(self, obj):
        return obj.patient.patient_id if obj.patient else ""
    
    def get_patient_phone(self, obj):
        return obj.patient.phone if obj.patient else ""
    
    def get_patient_age(self, obj):
        if obj.patient and obj.patient.date_of_birth:
            today = timezone.now().date()
            return today.year - obj.patient.date_of_birth.year
        return None
    
    def get_wait_time(self, obj):
        if obj.created_at:
            delta = timezone.now() - obj.created_at
            return int(delta.total_seconds() / 60)
        return 0
    
    def get_arrival_time(self, obj):
        return obj.created_at.strftime("%I:%M %p") if obj.created_at else ""


class DoctorPatientListSerializer(serializers.ModelSerializer):
    """Serializer for patient list in doctor panel"""
    
    name = serializers.SerializerMethodField()
    email = serializers.SerializerMethodField()
    last_visit = serializers.SerializerMethodField()
    total_visits = serializers.SerializerMethodField()
    status_display = serializers.SerializerMethodField()
    
    class Meta:
        model = PatientProfile
        fields = [
            'id', 'patient_id', 'name', 'email', 'phone', 
            'last_visit', 'total_visits', 'status', 'status_display'
        ]
    
    def get_name(self, obj):
        return obj.user.full_name if obj.user else ""
    
    def get_email(self, obj):
        return obj.user.email if obj.user else ""
    
    def get_last_visit(self, obj):
        last_ticket = obj.op_tickets.order_by('-date', '-created_at').first()
        if last_ticket and last_ticket.date:
            return last_ticket.date.strftime("%d %b %Y")
        return None
    
    def get_total_visits(self, obj):
        return obj.op_tickets.count()
    
    def get_status_display(self, obj):
        return obj.get_status_display()


class DoctorPatientDetailSerializer(serializers.ModelSerializer):
    """Detailed patient serializer with visit history"""
    
    name = serializers.SerializerMethodField()
    email = serializers.SerializerMethodField()
    age = serializers.SerializerMethodField()
    gender_display = serializers.SerializerMethodField()
    visit_history = serializers.SerializerMethodField()
    recent_emr_records = serializers.SerializerMethodField()
    
    class Meta:
        model = PatientProfile
        fields = [
            'id', 'patient_id', 'name', 'email', 'phone', 
            'age', 'gender', 'gender_display', 'blood_group', 
            'address', 'status', 'visit_history', 'recent_emr_records'
        ]
    
    def get_name(self, obj):
        return obj.user.full_name if obj.user else ""
    
    def get_email(self, obj):
        return obj.user.email if obj.user else ""
    
    def get_age(self, obj):
        if obj.date_of_birth:
            today = timezone.now().date()
            return today.year - obj.date_of_birth.year
        return None
    
    def get_gender_display(self, obj):
        return obj.get_gender_display() if obj.gender else None
    
    def get_visit_history(self, obj):
        tickets = obj.op_tickets.select_related('assigned_doctor').order_by('-date', '-created_at')[:20]
        return [
            {
                'date': t.date.strftime("%d %b %Y") if t.date else None,
                'token': t.token_number,
                'doctor': t.assigned_doctor.full_name if t.assigned_doctor else None,
                'reason': t.visit_reason,
                'status': t.status,
                'status_display': t.get_status_display(),
                'notes': t.notes
            }
            for t in tickets
        ]
    
    def get_recent_emr_records(self, obj):
        records = EMRRecord.objects.filter(patient=obj).order_by('-created_at')[:5]
        return [
            {
                'id': r.id,
                'type': r.get_record_type_display(),
                'title': r.title,
                'date': r.date.strftime("%d %b %Y") if r.date else None,
                'created_by': r.created_by.full_name if r.created_by else None
            }
            for r in records
        ]


class DoctorAppointmentSerializer(serializers.ModelSerializer):
    """Serializer for doctor's appointments"""
    
    patient_name = serializers.SerializerMethodField()
    patient_mrn = serializers.SerializerMethodField()
    patient_phone = serializers.SerializerMethodField()
    status_display = serializers.SerializerMethodField()
    
    class Meta:
        model = Appointment
        fields = [
            'id', 'appointment_id', 'appointment_date', 'appointment_time',
            'token_number', 'patient_name', 'patient_mrn', 'patient_phone',
            'visit_reason', 'status', 'status_display'
        ]
    
    def get_patient_name(self, obj):
        return obj.patient.user.full_name if obj.patient and obj.patient.user else ""
    
    def get_patient_mrn(self, obj):
        return obj.patient.patient_id if obj.patient else ""
    
    def get_patient_phone(self, obj):
        return obj.patient.phone if obj.patient else ""
    
    def get_status_display(self, obj):
        return obj.get_status_display()


class DoctorClinicalNoteSerializer(serializers.Serializer):
    """Serializer for creating clinical notes (SOAP format)"""
    
    patient_id = serializers.IntegerField()
    subjective = serializers.CharField(required=False, allow_blank=True)
    objective = serializers.CharField(required=False, allow_blank=True)
    assessment = serializers.CharField(required=False, allow_blank=True)
    plan = serializers.CharField(required=False, allow_blank=True)
    notes = serializers.CharField(required=False, allow_blank=True)
    
    def validate_patient_id(self, value):
        try:
            patient = PatientProfile.objects.get(id=value)
            return patient
        except PatientProfile.DoesNotExist:
            raise serializers.ValidationError("Patient not found")


class DoctorPrescriptionSerializer(serializers.Serializer):
    """Serializer for creating prescriptions"""
    
    patient_id = serializers.IntegerField()
    medication_name = serializers.CharField()
    dosage = serializers.CharField()
    frequency = serializers.CharField()
    duration = serializers.CharField()
    route = serializers.CharField()
    instructions = serializers.CharField(required=False, allow_blank=True)
    
    def validate_patient_id(self, value):
        try:
            patient = PatientProfile.objects.get(id=value)
            return patient
        except PatientProfile.DoesNotExist:
            raise serializers.ValidationError("Patient not found")


class DoctorStatsSerializer(serializers.Serializer):
    """Serializer for doctor statistics"""
    
    today_patients = serializers.IntegerField()
    waiting = serializers.IntegerField()
    in_consultation = serializers.IntegerField()
    completed_today = serializers.IntegerField()
    total_patients = serializers.IntegerField()
    weekly_patients = serializers.IntegerField()
    monthly_patients = serializers.IntegerField()
    average_consultation_time = serializers.IntegerField()