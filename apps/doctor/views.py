# apps/doctor/views.py - COMPLETE CORRECTED VERSION

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from django.db.models import Q, Count
from datetime import timedelta

from .permissions import IsDoctor
from .serializers import (
    DoctorQueueSerializer, DoctorPatientListSerializer,
    DoctorPatientDetailSerializer, DoctorAppointmentSerializer,
    DoctorClinicalNoteSerializer, DoctorPrescriptionSerializer,
    DoctorStatsSerializer
)
from appointments.models import OPTicket, Appointment
from patients.models import PatientProfile
from accounts.models import User
from emr.models import EMRRecord, ConsultationNote, Prescription
from appointments.models import Appointment
from accounts.models import User


class DoctorDashboardView(APIView):
    """Doctor's main dashboard - shows stats and today's queue"""
    permission_classes = [IsAuthenticated, IsDoctor]
    
    def get(self, request):
        doctor = request.user
        today = timezone.now().date()
        
        # Today's tickets for this doctor
        today_tickets = OPTicket.objects.filter(
            assigned_doctor=doctor,
            date=today
        ).select_related('patient__user')
        
        # Count stats
        waiting_count = today_tickets.filter(status='WAITING').count()
        in_consult_count = today_tickets.filter(status='IN_CONSULT').count()
        completed_count = today_tickets.filter(status='DONE').count()
        
        # Total unique patients for this doctor
        total_patients = PatientProfile.objects.filter(
            op_tickets__assigned_doctor=doctor
        ).distinct().count()
        
        # Weekly and monthly stats
        start_of_week = today - timedelta(days=today.weekday())
        start_of_month = today.replace(day=1)
        
        weekly_patients = PatientProfile.objects.filter(
            op_tickets__assigned_doctor=doctor,
            op_tickets__date__gte=start_of_week
        ).distinct().count()
        
        monthly_patients = PatientProfile.objects.filter(
            op_tickets__assigned_doctor=doctor,
            op_tickets__date__gte=start_of_month
        ).distinct().count()
        
        # Calculate average consultation time
        avg_consult_time = 15  # minutes
        
        # Queue data
        queue_tickets = today_tickets.filter(
            status__in=['WAITING', 'IN_CONSULT']
        ).order_by('token_number')
        
        queue_serializer = DoctorQueueSerializer(queue_tickets, many=True)
        
        # Role display name
        role_display = {
            'END': 'Reproductive Endocrinologist',
            'GYN': 'Gynaecologist',
            'ANE': 'Andrologist'
        }.get(doctor.role, 'Doctor')
        
        # Specialization
        specialization = {
            'END': 'Department of Advanced Reproduction',
            'GYN': 'Gynaecology',
            'ANE': 'Andrology'
        }.get(doctor.role, 'General Medicine')
        
        return Response({
            'success': True,
            'doctor': {
                'id': doctor.id,
                'name': doctor.full_name,
                'email': doctor.email,
                'role': doctor.role,
                'role_display': role_display,
                'specialization': specialization
            },
            'stats': {
                'today_patients': today_tickets.count(),
                'waiting': waiting_count,
                'in_consultation': in_consult_count,
                'completed_today': completed_count,
                'total_patients': total_patients,
                'weekly_patients': weekly_patients,
                'monthly_patients': monthly_patients,
                'average_consultation_time': avg_consult_time
            },
            'today_queue': queue_serializer.data
        })


class DoctorQueueView(APIView):
    """Manage doctor's queue - view, start, complete consultations"""
    permission_classes = [IsAuthenticated, IsDoctor]
    
    def get(self, request):
        """Get current queue status with completed patients details"""
        doctor = request.user
        today = timezone.now().date()
        
        # Current patient in consultation
        current_ticket = OPTicket.objects.filter(
            assigned_doctor=doctor,
            date=today,
            status='IN_CONSULT'
        ).select_related('patient__user').first()
        
        # Waiting patients
        waiting_tickets = OPTicket.objects.filter(
            assigned_doctor=doctor,
            date=today,
            status='WAITING'
        ).select_related('patient__user').order_by('token_number')
        
        # Completed today with details
        completed_tickets = OPTicket.objects.filter(
            assigned_doctor=doctor,
            date=today,
            status='DONE'
        ).select_related('patient__user', 'department').order_by('-updated_at')
        
        current_data = None
        if current_ticket:
            current_data = {
                'id': current_ticket.id,
                'token': current_ticket.token_number,
                'patient_name': current_ticket.patient.user.full_name,
                'patient_mrn': current_ticket.patient.patient_id,
                'visit_reason': current_ticket.visit_reason,
                'started_at': current_ticket.updated_at.isoformat() if current_ticket.updated_at else None
            }
        
        # Build completed patients list
        completed_list = []
        for ticket in completed_tickets:
            completed_list.append({
                'id': ticket.id,
                'token': ticket.token_number,
                'patient_name': ticket.patient.user.full_name,
                'patient_mrn': ticket.patient.patient_id,
                'patient_phone': ticket.patient.phone or '',
                'visit_reason': ticket.visit_reason,
                'completed_at': ticket.updated_at.strftime('%I:%M %p') if ticket.updated_at else None,
                'department': ticket.department.name if ticket.department else None,
                'notes': ticket.notes
            })
        
        return Response({
            'success': True,
            'current_patient': current_data,
            'waiting_queue': DoctorQueueSerializer(waiting_tickets, many=True).data,
            'completed_count': completed_tickets.count(),
            'completed_patients': completed_list,
            'total_waiting': waiting_tickets.count()
        })
    
    def post(self, request):
        """Start or complete consultation"""
        doctor = request.user
        ticket_id = request.data.get('ticket_id')
        action = request.data.get('action')  # 'start' or 'complete'
        
        if not ticket_id or not action:
            return Response({
                'error': 'ticket_id and action are required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            ticket = OPTicket.objects.get(id=ticket_id, assigned_doctor=doctor)
        except OPTicket.DoesNotExist:
            return Response({
                'error': 'Ticket not found or not assigned to you'
            }, status=status.HTTP_404_NOT_FOUND)
        
        if action == 'start':
            if ticket.status != 'WAITING':
                return Response({
                    'error': f'Cannot start consultation. Current status: {ticket.get_status_display()}'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            ticket.status = 'IN_CONSULT'
            ticket.save()
            
            return Response({
                'success': True,
                'message': 'Consultation started',
                'ticket': {
                    'id': ticket.id,
                    'token': ticket.token_number,
                    'patient_name': ticket.patient.user.full_name,
                    'status': ticket.status,
                    'status_display': ticket.get_status_display()
                }
            })
        
        elif action == 'complete':
            if ticket.status != 'IN_CONSULT':
                return Response({
                    'error': f'Cannot complete consultation. Current status: {ticket.get_status_display()}'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            ticket.status = 'DONE'
            ticket.save()
            
            return Response({
                'success': True,
                'message': 'Consultation completed',
                'ticket': {
                    'id': ticket.id,
                    'token': ticket.token_number,
                    'patient_name': ticket.patient.user.full_name,
                    'status': ticket.status,
                    'status_display': ticket.get_status_display()
                }
            })
        
        else:
            return Response({
                'error': 'Invalid action. Use "start" or "complete"'
            }, status=status.HTTP_400_BAD_REQUEST)


class DoctorCompletedPatientsView(APIView):
    """Get completed patients details for grid display"""
    permission_classes = [IsAuthenticated, IsDoctor]
    
    def get(self, request):
        doctor = request.user
        today = timezone.now().date()
        
        # Get filter parameters
        date = request.query_params.get('date')
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        
        # Base query - completed tickets for this doctor
        completed_tickets = OPTicket.objects.filter(
            assigned_doctor=doctor,
            status='DONE'
        ).select_related('patient__user', 'department')
        
        # Apply date filters
        if date:
            completed_tickets = completed_tickets.filter(date=date)
        elif start_date and end_date:
            completed_tickets = completed_tickets.filter(
                date__gte=start_date,
                date__lte=end_date
            )
        else:
            completed_tickets = completed_tickets.filter(date=today)
        
        # Order by completed time (most recent first)
        completed_tickets = completed_tickets.order_by('-updated_at')
        
        # Prepare response data
        completed_list = []
        for ticket in completed_tickets:
            completed_list.append({
                'id': ticket.id,
                'token_number': ticket.token_number,
                'patient_id': ticket.patient.id,
                'patient_name': ticket.patient.user.full_name,
                'patient_mrn': ticket.patient.patient_id,
                'patient_phone': ticket.patient.phone or '',
                'patient_age': self.calculate_age(ticket.patient.date_of_birth),
                'patient_gender': ticket.patient.gender,
                'visit_reason': ticket.visit_reason,
                'visit_reason_display': ticket.get_visit_reason_display(),
                'department': ticket.department.name if ticket.department else None,
                'notes': ticket.notes,
                'completed_at': ticket.updated_at.strftime('%I:%M %p') if ticket.updated_at else None,
                'completed_date': ticket.date.strftime('%d %b %Y') if ticket.date else None,
                'duration': self.calculate_duration(ticket.created_at, ticket.updated_at)
            })
        
        return Response({
            'success': True,
            'total_count': completed_tickets.count(),
            'completed_patients': completed_list,
            'filters': {
                'date': date or str(today),
                'start_date': start_date,
                'end_date': end_date
            }
        })
    
    def calculate_age(self, date_of_birth):
        if not date_of_birth:
            return None
        today = timezone.now().date()
        return today.year - date_of_birth.year - ((today.month, today.day) < (date_of_birth.month, date_of_birth.day))
    
    def calculate_duration(self, start_time, end_time):
        """Calculate consultation duration in minutes"""
        if start_time and end_time:
            delta = end_time - start_time
            minutes = int(delta.total_seconds() / 60)
            if minutes < 60:
                return f"{minutes} min"
            else:
                hours = minutes // 60
                mins = minutes % 60
                return f"{hours}h {mins}m"
        return None


class DoctorPatientsView(APIView):
    """Get list of doctor's patients with pagination, search, filters, and statistics"""
    permission_classes = [IsAuthenticated, IsDoctor]
    
    def get(self, request):
        doctor = request.user
        
        # Get query parameters with defaults
        search = request.query_params.get('search', '')
        status_filter = request.query_params.get('status', '')
        treatment_filter = request.query_params.get('treatment', '')  # 🆕 Add treatment filter
        sort_by = request.query_params.get('sort_by', '-last_visit')
        page = int(request.query_params.get('page', 1))
        page_size = int(request.query_params.get('page_size', 20))
        
        # Get distinct patients who had tickets with this doctor
        all_patients = PatientProfile.objects.filter(
            op_tickets__assigned_doctor=doctor
        ).distinct().select_related('user')
        
        # ========== CALCULATE STATISTICS ==========
        today = timezone.now().date()
        start_of_week = today - timedelta(days=today.weekday())
        start_of_month = today.replace(day=1)
        
        # Total counts
        total_patients = all_patients.count()
        active_treatments = all_patients.filter(status='ACTIVE').count()
        completed_treatments = all_patients.filter(status='COMPLETED').count()
        
        # Patients registered this week
        this_week_patients = all_patients.filter(
            registered_on__gte=start_of_week
        ).count()
        
        # Patients registered this month
        this_month_patients = all_patients.filter(
            registered_on__gte=start_of_month
        ).count()
        
        # ========== COMPLETED PATIENTS COUNT FOR TODAY ==========
        completed_today_count = OPTicket.objects.filter(
            assigned_doctor=doctor,
            status='DONE',
            date=today
        ).count()
        
        # ========== APPLY FILTERS FOR PATIENT LIST ==========
        patients = all_patients
        
        # Apply search filter
        if search:
            patients = patients.filter(
                Q(user__full_name__icontains=search) |
                Q(patient_id__icontains=search) |
                Q(phone__icontains=search)
            )
        
        # Apply status filter
        if status_filter:
            patients = patients.filter(status=status_filter)
        
        # 🆕 Apply treatment type filter
        if treatment_filter:
            patients = patients.filter(treatment_type=treatment_filter)
        
        # Annotate with last visit date and total visits for sorting
        from django.db.models import Max, Count
        patients = patients.annotate(
            last_visit_date=Max('op_tickets__date'),
            total_visits=Count('op_tickets')
        )
        
        # Apply sorting
        if sort_by == 'name':
            patients = patients.order_by('user__full_name')
        elif sort_by == '-name':
            patients = patients.order_by('-user__full_name')
        elif sort_by == 'last_visit':
            patients = patients.order_by('last_visit_date')
        elif sort_by == '-last_visit':
            patients = patients.order_by('-last_visit_date')
        elif sort_by == 'total_visits':
            patients = patients.order_by('-total_visits')
        else:
            patients = patients.order_by('-last_visit_date')
        
        # Get total count for pagination
        total = patients.count()
        total_pages = (total + page_size - 1) // page_size if page_size > 0 else 1
        
        # Apply pagination
        start = (page - 1) * page_size
        end = start + page_size
        paginated_patients = patients[start:end]
        
        # Build response with treatment type
        result = []
        for patient in paginated_patients:
            result.append({
                'id': patient.id,
                'patient_id': patient.patient_id,
                'name': patient.user.full_name,
                'email': patient.user.email,
                'phone': patient.phone or '',
                'last_visit': patient.last_visit_date.strftime('%d %b %Y') if patient.last_visit_date else None,
                'total_visits': patient.total_visits,
                'status': patient.status,
                'status_display': patient.get_status_display(),
                'treatment_type': patient.treatment_type,  # 🆕 Add treatment type code
                'treatment_display': patient.get_treatment_type_display() if patient.treatment_type else None,  # 🆕 Add display name
            })
        
        return Response({
            'success': True,
            # ========== STATISTICS CARDS DATA ==========
            'statistics': {
                'total_patients': total_patients,
                'active_treatments': active_treatments,
                'completed_treatments': completed_treatments,
                'this_week_patients': this_week_patients,
                'this_month_patients': this_month_patients,
                'completed_today_count': completed_today_count,
            },
            # ========== PAGINATION INFO ==========
            'total': total,
            'page': page,
            'page_size': page_size,
            'total_pages': total_pages,
            # ========== PATIENT LIST WITH TREATMENT TYPE ==========
            'patients': result
        })

class DoctorPatientDetailView(APIView):
    """Get detailed patient information with visit history"""
    permission_classes = [IsAuthenticated, IsDoctor]
    
    def get(self, request, patient_id):
        doctor = request.user
        
        try:
            patient = PatientProfile.objects.get(id=patient_id)
        except PatientProfile.DoesNotExist:
            return Response({
                'error': 'Patient not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Verify this patient belongs to this doctor
        if not patient.op_tickets.filter(assigned_doctor=doctor).exists():
            return Response({
                'error': 'Patient not found for this doctor'
            }, status=status.HTTP_404_NOT_FOUND)
        
        serializer = DoctorPatientDetailSerializer(patient)
        
        return Response({
            'success': True,
            'patient': serializer.data
        })


class DoctorAppointmentsView(APIView):
    """Get doctor's appointments"""
    permission_classes = [IsAuthenticated, IsDoctor]
    
    def get(self, request):
        doctor = request.user
        today = timezone.now().date()
        
        # Get date range parameter
        date_range = request.query_params.get('range', 'today')
        
        if date_range == 'today':
            appointments = Appointment.objects.filter(
                doctor=doctor,
                appointment_date=today
            ).select_related('patient__user').order_by('appointment_time', 'token_number')
        
        elif date_range == 'upcoming':
            next_week = today + timedelta(days=7)
            appointments = Appointment.objects.filter(
                doctor=doctor,
                appointment_date__gte=today,
                appointment_date__lte=next_week,
                status__in=['SCHEDULED', 'CONFIRMED']
            ).select_related('patient__user').order_by('appointment_date', 'appointment_time')
        
        else:
            appointments = Appointment.objects.filter(
                doctor=doctor
            ).select_related('patient__user').order_by('-appointment_date', 'appointment_time')[:50]
        
        serializer = DoctorAppointmentSerializer(appointments, many=True)
        
        return Response({
            'success': True,
            'range': date_range,
            'count': appointments.count(),
            'appointments': serializer.data
        })


class DoctorClinicalNotesView(APIView):
    """Create and manage clinical notes (SOAP format)"""
    permission_classes = [IsAuthenticated, IsDoctor]
    
    def post(self, request):
        """Create a clinical note for a patient"""
        doctor = request.user
        serializer = DoctorClinicalNoteSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        patient = serializer.validated_data['patient_id']
        
        # Create EMR record for consultation note
        emr_record = EMRRecord.objects.create(
            patient=patient,
            record_type='CONSULTATION',
            title=f"Consultation - {timezone.now().strftime('%d %b %Y')}",
            date=timezone.now().date(),
            notes=serializer.validated_data.get('notes', ''),
            created_by=doctor
        )
        
        # Create consultation note with SOAP format
        consultation_note = ConsultationNote.objects.create(
            record=emr_record,
            chief_complaint=serializer.validated_data.get('subjective', ''),
            history=serializer.validated_data.get('objective', ''),
            examination=serializer.validated_data.get('assessment', ''),
            plan=serializer.validated_data.get('plan', '')
        )
        
        return Response({
            'success': True,
            'message': 'Clinical note saved successfully',
            'note': {
                'id': emr_record.id,
                'patient': patient.patient_id,
                'patient_name': patient.user.full_name,
                'date': emr_record.date,
                'subjective': consultation_note.chief_complaint,
                'objective': consultation_note.history,
                'assessment': consultation_note.examination,
                'plan': consultation_note.plan
            }
        }, status=status.HTTP_201_CREATED)
    
    def get(self, request):
        """Get clinical notes for a patient with full details"""
        doctor = request.user
        patient_id = request.query_params.get('patient_id')
        
        if not patient_id:
            return Response({
                'error': 'patient_id is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            patient = PatientProfile.objects.get(id=patient_id)
        except PatientProfile.DoesNotExist:
            return Response({'error': 'Patient not found'}, status=404)
        
        # Verify this patient belongs to this doctor
        if not patient.op_tickets.filter(assigned_doctor=doctor).exists():
            return Response({
                'error': 'Patient not found for this doctor'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Get all consultation notes for this patient
        records = EMRRecord.objects.filter(
            patient=patient,
            record_type='CONSULTATION'
        ).select_related('created_by').order_by('-created_at')
        
        notes = []
        for record in records:
            consultation = record.consultation
            if consultation:
                notes.append({
                    'id': record.id,
                    'patient_id': patient.patient_id,
                    'patient_name': patient.user.full_name,
                    'title': record.title,
                    'date': record.date,
                    'subjective': consultation.chief_complaint,
                    'objective': consultation.history,
                    'assessment': consultation.examination,
                    'plan': consultation.plan,
                    'notes': record.notes,
                    'created_by': record.created_by.full_name if record.created_by else None,
                    'created_at': record.created_at
                })
        
        return Response({
            'success': True,
            'count': len(notes),
            'notes': notes
        })


class DoctorPrescriptionsView(APIView):
    """Create and manage prescriptions"""
    permission_classes = [IsAuthenticated, IsDoctor]
    
    def post(self, request):
        """Create a prescription for a patient"""
        doctor = request.user
        serializer = DoctorPrescriptionSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        patient = serializer.validated_data['patient_id']
        
        # Create EMR record for prescription
        emr_record = EMRRecord.objects.create(
            patient=patient,
            record_type='PRESCRIPTION',
            title=f"Prescription - {serializer.validated_data['medication_name']}",
            date=timezone.now().date(),
            created_by=doctor
        )
        
        # Create prescription
        prescription = Prescription.objects.create(
            record=emr_record,
            medication_name=serializer.validated_data['medication_name'],
            dosage=serializer.validated_data['dosage'],
            frequency=serializer.validated_data['frequency'],
            duration=serializer.validated_data['duration'],
            route=serializer.validated_data['route'],
            instructions=serializer.validated_data.get('instructions', '')
        )
        
        return Response({
            'success': True,
            'message': 'Prescription created successfully',
            'prescription': {
                'id': prescription.id,
                'patient': patient.patient_id,
                'patient_name': patient.user.full_name,
                'medication': prescription.medication_name,
                'dosage': prescription.dosage,
                'frequency': prescription.frequency,
                'duration': prescription.duration,
                'route': prescription.route,
                'instructions': prescription.instructions,
                'date': emr_record.date
            }
        }, status=status.HTTP_201_CREATED)
    
    def get(self, request):
        """Get prescriptions - either for a specific patient OR all prescriptions by this doctor"""
        doctor = request.user
        patient_id = request.query_params.get('patient_id')
        
        # ✅ If patient_id is provided, return prescriptions for that specific patient
        if patient_id:
            try:
                patient = PatientProfile.objects.get(id=patient_id)
            except PatientProfile.DoesNotExist:
                return Response({'error': 'Patient not found'}, status=status.HTTP_404_NOT_FOUND)
            
            # Get prescriptions for this specific patient (by this doctor)
            records = EMRRecord.objects.filter(
                patient=patient,
                record_type='PRESCRIPTION',
                created_by=doctor
            ).select_related('created_by').prefetch_related('prescriptions').order_by('-created_at')
            
            prescriptions = []
            for record in records:
                # Get ALL prescriptions for each record
                for prescription in record.prescriptions.all():
                    prescriptions.append({
                        'id': prescription.id,
                        'medication': prescription.medication_name,
                        'dosage': prescription.dosage,
                        'frequency': prescription.frequency,
                        'duration': prescription.duration,
                        'route': prescription.route,
                        'instructions': prescription.instructions,
                        'date': record.date.strftime('%Y-%m-%d'),
                        'prescribed_by': record.created_by.full_name if record.created_by else None
                    })
            
            return Response({
                'success': True,
                'patient': {
                    'id': patient.id,
                    'name': patient.user.full_name,
                    'mrn': patient.patient_id
                },
                'count': len(prescriptions),
                'prescriptions': prescriptions
            })
        
        # ✅ NEW: Get ALL prescriptions prescribed by this doctor (for all patients)
        # This is for the prescription history page
        records = EMRRecord.objects.filter(
            record_type='PRESCRIPTION',
            created_by=doctor  # Only this doctor's prescriptions
        ).select_related('patient__user', 'created_by').prefetch_related('prescriptions').order_by('-created_at')
        
        prescriptions = []
        for record in records:
            for prescription in record.prescriptions.all():
                # Calculate status (active/expired based on duration)
                status = self.get_prescription_status(record.date, prescription.duration)
                
                prescriptions.append({
                    'id': prescription.id,
                    'prescription_id': f"RX-{prescription.id}",  # Format as RX-1, RX-2, etc.
                    'patient_mrn': record.patient.patient_id,
                    'patient_name': record.patient.user.full_name,
                    'prescribed_date': record.date.strftime('%Y-%m-%d'),
                    'medicine': prescription.medication_name,
                    'dosage': prescription.dosage,
                    'duration': prescription.duration,
                    'status': status,
                    'frequency': prescription.frequency,
                    'route': prescription.route,
                    'instructions': prescription.instructions,
                    'prescribed_by': record.created_by.full_name if record.created_by else None
                })
        
        # Calculate summary statistics for the dashboard cards
        active_count = len([p for p in prescriptions if p['status'] == 'Active'])
        patients_set = set([p['patient_mrn'] for p in prescriptions])
        today_count = len([p for p in prescriptions if p['prescribed_date'] == str(timezone.now().date())])
        
        return Response({
            'success': True,
            'count': len(prescriptions),
            'prescriptions': prescriptions,
            'summary': {
                'total_prescriptions': len(prescriptions),
                'active_medications': active_count,
                'patients_prescribed': len(patients_set),
                'issued_today': today_count
            }
        })
    
    def get_prescription_status(self, prescribed_date, duration):
        """Calculate if prescription is active or expired based on duration"""
        try:
            import re
            # Extract number from duration (e.g., "5 days" -> 5, "10" -> 10)
            numbers = re.findall(r'\d+', str(duration))
            if numbers:
                days = int(numbers[0])
                expiry_date = prescribed_date + timedelta(days=days)
                if expiry_date >= timezone.now().date():
                    return 'Active'
                else:
                    return 'Expired'
            else:
                # If no number found, assume active
                return 'Active'
        except:
            return 'Active'
# apps/doctor/views.py - Replace your existing DoctorProfileView with this

# apps/doctor/views.py - Replace your DoctorProfileView with this

class DoctorProfileView(APIView):
    """Get, update doctor's profile and change password"""
    permission_classes = [IsAuthenticated, IsDoctor]
    
    def get(self, request):
        """Get doctor's profile information"""
        doctor = request.user
        
        # Role names
        role_names = {
            'END': 'Reproductive Endocrinologist',
            'GYN': 'Gynaecologist',
            'ANE': 'Andrologist'
        }
        
        # Get role-specific profile data
        profile_data = {}
        contact_number = None
        
        if doctor.role == 'END' and hasattr(doctor, 'endocrinologist_profile'):
            prof = doctor.endocrinologist_profile
            profile_data = {
                'employee_id': prof.employee_id,
                'can_perform_egg_retrieval': prof.can_perform_egg_retrieval,
                'can_perform_embryo_transfer': prof.can_perform_embryo_transfer,
                'can_design_ivf_protocols': prof.can_design_ivf_protocols,
                'is_department_head': prof.is_department_head
            }
            # Get contact number if field exists
            if hasattr(prof, 'contact_number'):
                contact_number = prof.contact_number
                
        elif doctor.role == 'GYN' and hasattr(doctor, 'gynaec_profile'):
            prof = doctor.gynaec_profile
            profile_data = {
                'employee_id': prof.employee_id,
                'can_perform_egg_retrieval': prof.can_perform_egg_retrieval,
                'can_assist_ivf': prof.can_assist_ivf,
                'is_department_head': prof.is_department_head
            }
            # Get contact number if field exists
            if hasattr(prof, 'contact_number'):
                contact_number = prof.contact_number
                
        elif doctor.role == 'ANE' and hasattr(doctor, 'anesth_profile'):
            prof = doctor.anesth_profile
            profile_data = {
                'employee_id': prof.employee_id,
                'can_edit_anesthesia_records': prof.can_edit_anesthesia_records,
                'is_department_head': prof.is_department_head
            }
            # Get contact number if field exists
            if hasattr(prof, 'contact_number'):
                contact_number = prof.contact_number
        
        # Get department info
        department_info = []
        for assignment in doctor.staff_assignments.filter(is_active=True).select_related('department'):
            department_info.append({
                'id': assignment.department.id,
                'name': assignment.department.name,
                'code': assignment.department.code,
                'role': assignment.role_in_dept
            })
        
        return Response({
            'success': True,
            'profile': {
                'id': doctor.id,
                'name': doctor.full_name,
                'email': doctor.email,
                'role': doctor.role,
                'role_display': role_names.get(doctor.role, 'Doctor'),
                'is_active': doctor.is_active,
                'date_joined': doctor.date_joined,
                'contact_number': contact_number or '',
                'departments': department_info,
                **profile_data
            }
        })
    
    def put(self, request):
        """Update doctor's profile"""
        doctor = request.user
        
        # Get data from request
        full_name = request.data.get('full_name')
        contact_number = request.data.get('contact_number')
        
        # Update user full name
        if full_name:
            doctor.full_name = full_name
            doctor.save()
        
        # Update contact number in role-specific profile
        if contact_number:
            if doctor.role == 'END' and hasattr(doctor, 'endocrinologist_profile'):
                prof = doctor.endocrinologist_profile
                if hasattr(prof, 'contact_number'):
                    prof.contact_number = contact_number
                    prof.save()
            elif doctor.role == 'GYN' and hasattr(doctor, 'gynaec_profile'):
                prof = doctor.gynaec_profile
                if hasattr(prof, 'contact_number'):
                    prof.contact_number = contact_number
                    prof.save()
            elif doctor.role == 'ANE' and hasattr(doctor, 'anesth_profile'):
                prof = doctor.anesth_profile
                if hasattr(prof, 'contact_number'):
                    prof.contact_number = contact_number
                    prof.save()
        
        # Get updated profile data
        role_names = {
            'END': 'Reproductive Endocrinologist',
            'GYN': 'Gynaecologist',
            'ANE': 'Andrologist'
        }
        
        return Response({
            'success': True,
            'message': 'Profile updated successfully',
            'profile': {
                'id': doctor.id,
                'name': doctor.full_name,
                'email': doctor.email,
                'role': doctor.role,
                'role_display': role_names.get(doctor.role, 'Doctor'),
                'contact_number': contact_number or '',
                'is_active': doctor.is_active,
                'date_joined': doctor.date_joined
            }
        })


class DoctorChangePasswordView(APIView):
    """Doctor change password"""
    permission_classes = [IsAuthenticated, IsDoctor]
    
    def post(self, request):
        doctor = request.user
        
        # Get data from request
        old_password = request.data.get('old_password')
        new_password = request.data.get('new_password')
        confirm_password = request.data.get('confirm_password')
        
        # Validate required fields
        if not old_password:
            return Response({
                'error': 'Current password is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if not new_password:
            return Response({
                'error': 'New password is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if not confirm_password:
            return Response({
                'error': 'Please confirm your new password'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Check if new passwords match
        if new_password != confirm_password:
            return Response({
                'error': 'New passwords do not match'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Check password length
        if len(new_password) < 6:
            return Response({
                'error': 'Password must be at least 6 characters'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Verify old password
        if not doctor.check_password(old_password):
            return Response({
                'error': 'Current password is incorrect'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Set new password
        doctor.set_password(new_password)
        doctor.save()
        
        # Update session to prevent logout
        from django.contrib.auth import update_session_auth_hash
        update_session_auth_hash(request, doctor)
        
        return Response({
            'success': True,
            'message': 'Password changed successfully'
        })
class DoctorCalendarView(APIView):
    """
    Doctor's personal calendar - Shows schedule AND approved leaves
    GET /api/doctor/calendar/?start_date=2026-06-15&end_date=2026-06-21
    """
    permission_classes = [IsAuthenticated, IsDoctor]
    
    def get(self, request):
        doctor = request.user
        start_date_str = request.query_params.get('start_date')
        end_date_str = request.query_params.get('end_date')
        
        if not start_date_str or not end_date_str:
            return Response({
                'error': 'start_date and end_date are required',
                'format': 'YYYY-MM-DD',
                'example': '/api/doctor/calendar/?start_date=2026-06-15&end_date=2026-06-21'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            start_date = timezone.datetime.strptime(start_date_str, '%Y-%m-%d').date()
            end_date = timezone.datetime.strptime(end_date_str, '%Y-%m-%d').date()
        except ValueError:
            return Response({
                'error': 'Invalid date format. Use YYYY-MM-DD'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Time slots
        time_slots = [
            '09:00 AM', '09:30 AM', '10:00 AM', '10:30 AM',
            '11:00 AM', '11:30 AM', '12:00 PM', '12:30 PM',
            '02:00 PM', '02:30 PM', '03:00 PM', '03:30 PM',
            '04:00 PM', '04:30 PM'
        ]
        
        # Get appointments for this doctor only
        appointments = Appointment.objects.filter(
            doctor=doctor,
            appointment_date__gte=start_date,
            appointment_date__lte=end_date
        ).select_related('patient__user').order_by('appointment_date', 'appointment_time')
        
        # ========== GET APPROVED LEAVES FOR THIS DOCTOR ==========
        try:
            from hr.models import LeaveRequest
            
            approved_leaves = LeaveRequest.objects.filter(
                employee=doctor,
                status='APPROVED',
                start_date__lte=end_date,
                end_date__gte=start_date
            )
        except ImportError:
            approved_leaves = []
        
        # Build calendar view
        calendar_view = []
        current_date = start_date
        
        while current_date <= end_date:
            day_appointments = appointments.filter(appointment_date=current_date)
            
            # Check if this date falls within any approved leave
            is_leave_date = False
            leave_info = None
            for leave in approved_leaves:
                if leave.start_date <= current_date <= leave.end_date:
                    is_leave_date = True
                    leave_info = {
                        'id': leave.id,
                        'leave_type': leave.get_leave_type_display(),
                        'reason': leave.reason,
                        'status': leave.status
                    }
                    break
            
            slots = []
            for slot in time_slots:
                appointment = day_appointments.filter(time_slot=slot).first()
                
                if is_leave_date:
                    # If on leave, mark all slots as leave (unavailable)
                    slots.append({
                        'time': slot,
                        'appointment': None,
                        'available': False,
                        'is_leave': True,
                        'leave_info': leave_info,
                        'reason': 'On Approved Leave'
                    })
                else:
                    slots.append({
                        'time': slot,
                        'appointment': {
                            'id': appointment.id if appointment else None,
                            'appointment_id': appointment.appointment_id if appointment else None,
                            'patient_name': appointment.patient.user.full_name if appointment else None,
                            'patient_mrn': appointment.patient.patient_id if appointment else None,
                            'status': appointment.status if appointment else None,
                            'status_display': appointment.get_status_display() if appointment else None,
                        } if appointment else None,
                        'available': appointment is None,
                        'is_leave': False
                    })
            
            calendar_view.append({
                'date': str(current_date),
                'day_name': current_date.strftime('%A'),
                'slots': slots,
                'total_appointments': day_appointments.count(),
                'available_slots': len([s for s in slots if s.get('available', False) and not s.get('is_leave', False)]),
                'is_leave': is_leave_date,
                'leave_info': leave_info
            })
            
            current_date += timedelta(days=1)
        
        # Get upcoming leaves for notification
        upcoming_leaves = []
        for leave in approved_leaves:
            if leave.start_date >= timezone.now().date():
                upcoming_leaves.append({
                    'id': leave.id,
                    'leave_type': leave.get_leave_type_display(),
                    'start_date': leave.start_date,
                    'end_date': leave.end_date,
                    'days': (leave.end_date - leave.start_date).days + 1,
                    'reason': leave.reason
                })
        
        return Response({
            'success': True,
            'start_date': str(start_date),
            'end_date': str(end_date),
            'doctor': {
                'id': doctor.id,
                'name': doctor.full_name,
                'specialization': doctor.get_role_display()
            },
            'calendar': calendar_view,
            'upcoming_leaves': upcoming_leaves,
            'leave_summary': {
                'total_approved_leaves': len(approved_leaves),
                'upcoming_leaves_count': len(upcoming_leaves)
            }
        })

class DoctorLeaveRequestView(APIView):
    """Doctor can request leave and view their leave requests"""
    permission_classes = [IsAuthenticated, IsDoctor]
    
    def post(self, request):
        """Submit a leave request"""
        doctor = request.user
        
        leave_type = request.data.get('leave_type')
        start_date = request.data.get('start_date')
        end_date = request.data.get('end_date')
        reason = request.data.get('reason', '')
        
        # Validate required fields
        if not leave_type:
            return Response({
                'error': 'leave_type is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if not start_date:
            return Response({
                'error': 'start_date is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if not end_date:
            return Response({
                'error': 'end_date is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Validate dates
        try:
            start = timezone.datetime.strptime(start_date, '%Y-%m-%d').date()
            end = timezone.datetime.strptime(end_date, '%Y-%m-%d').date()
        except ValueError:
            return Response({
                'error': 'Invalid date format. Use YYYY-MM-DD'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if start < timezone.now().date():
            return Response({
                'error': 'Start date cannot be in the past'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if end < start:
            return Response({
                'error': 'End date must be after start date'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Import LeaveRequest model (lazy import to avoid circular import)
        try:
            from hr.models import LeaveRequest
        except ImportError:
            return Response({
                'error': 'LeaveRequest model not found'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        # Create leave request
        leave = LeaveRequest.objects.create(
            employee=doctor,
            leave_type=leave_type,
            start_date=start,
            end_date=end,
            reason=reason,
            status='PENDING'
        )
        
        return Response({
            'success': True,
            'message': 'Leave request submitted successfully',
            'leave': {
                'id': leave.id,
                'leave_type': leave.leave_type,
                'leave_type_display': leave.get_leave_type_display(),
                'start_date': leave.start_date,
                'end_date': leave.end_date,
                'reason': leave.reason,
                'status': leave.status,
                'status_display': leave.get_status_display(),
                'created_at': leave.created_at
            }
        }, status=status.HTTP_201_CREATED)
    
    def get(self, request):
        """Get doctor's own leave requests"""
        doctor = request.user
        
        try:
            from hr.models import LeaveRequest
        except ImportError:
            return Response({
                'error': 'LeaveRequest model not found'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        leaves = LeaveRequest.objects.filter(employee=doctor).order_by('-created_at')
        
        leave_list = []
        for leave in leaves:
            # Calculate days
            delta = leave.end_date - leave.start_date
            days = delta.days + 1
            
            leave_list.append({
                'id': leave.id,
                'leave_type': leave.leave_type,
                'leave_type_display': leave.get_leave_type_display(),
                'start_date': leave.start_date,
                'end_date': leave.end_date,
                'days': days,
                'reason': leave.reason,
                'status': leave.status,
                'status_display': leave.get_status_display(),
                'created_at': leave.created_at,
                'approved_by': leave.approved_by.full_name if leave.approved_by else None,
                'approved_at': leave.approved_at,
                'rejection_reason': leave.rejection_reason
            })
        
        # Calculate leave balance for current year
        current_year = timezone.now().year
        approved_leaves = LeaveRequest.objects.filter(
            employee=doctor,
            status='APPROVED',
            start_date__year=current_year
        )
        
        total_taken = 0
        for leave in approved_leaves:
            delta = leave.end_date - leave.start_date
            total_taken += delta.days + 1
        
        leave_balance = {
            'annual': max(0, 20 - total_taken),
            'sick': 12,
            'casual': 10,
            'total_taken': total_taken,
            'total_remaining': max(0, 42 - total_taken)
        }
        
        return Response({
            'success': True,
            'leave_balance': leave_balance,
            'total': leaves.count(),
            'leaves': leave_list
        })


class DoctorLeaveBalanceView(APIView):
    """Get doctor's leave balance only"""
    permission_classes = [IsAuthenticated, IsDoctor]
    
    def get(self, request):
        doctor = request.user
        current_year = timezone.now().year
        
        try:
            from hr.models import LeaveRequest
        except ImportError:
            return Response({
                'error': 'LeaveRequest model not found'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        approved_leaves = LeaveRequest.objects.filter(
            employee=doctor,
            status='APPROVED',
            start_date__year=current_year
        )
        
        total_taken = 0
        for leave in approved_leaves:
            delta = leave.end_date - leave.start_date
            total_taken += delta.days + 1
        
        return Response({
            'success': True,
            'year': current_year,
            'leave_balance': {
                'annual': max(0, 20 - total_taken),
                'sick': 12,
                'casual': 10,
                'total_taken': total_taken,
                'total_remaining': max(0, 42 - total_taken)
            }
        })


class DoctorCancelLeaveView(APIView):
    """Doctor can cancel a pending leave request"""
    permission_classes = [IsAuthenticated, IsDoctor]
    
    def post(self, request, leave_id):
        doctor = request.user
        
        try:
            from hr.models import LeaveRequest
        except ImportError:
            return Response({
                'error': 'LeaveRequest model not found'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        try:
            leave = LeaveRequest.objects.get(id=leave_id, employee=doctor)
        except LeaveRequest.DoesNotExist:
            return Response({
                'error': 'Leave request not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        if leave.status != 'PENDING':
            return Response({
                'error': f'Cannot cancel leave that is already {leave.status.lower()}'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        leave.status = 'CANCELLED'
        leave.save()
        
        return Response({
            'success': True,
            'message': 'Leave request cancelled successfully',
            'leave': {
                'id': leave.id,
                'status': leave.status,
                'status_display': leave.get_status_display()
            }
        })

# ========== MEDICINE INVENTORY VIEW FOR DOCTOR PORTAL ==========

# ========== MEDICINE INVENTORY VIEW FOR DOCTOR PORTAL ==========

# ========== MEDICINE INVENTORY VIEW FOR DOCTOR PORTAL ==========

# ========== MEDICINE INVENTORY VIEW FOR DOCTOR PORTAL ==========

class DoctorMedicineInventoryView(APIView):
    """
    Get medicine inventory overview for doctor portal
    GET /api/doctor/medicines/ - List all medicines with filters
    GET /api/doctor/medicines/{id}/ - Get single medicine details
    """
    permission_classes = [IsAuthenticated, IsDoctor]
    
    def get(self, request, id=None):
        """Get medicines list or single medicine details"""
        
        # If ID is provided, get single medicine
        if id:
            try:
                from pharmacy.models import Medication
                medication = Medication.objects.select_related(
                    'category', 'manufacturer'
                ).get(id=id, is_active=True)
            except ImportError:
                return Response({
                    'success': False,
                    'error': 'Pharmacy module not available'
                }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
            except Medication.DoesNotExist:
                return Response({
                    'success': False,
                    'error': 'Medicine not found'
                }, status=status.HTTP_404_NOT_FOUND)
            
            return Response({
                'success': True,
                'data': {
                    'id': medication.id,
                    'medication_id': medication.medication_id,
                    'name': medication.name,
                    'generic_name': medication.generic_name,
                    'category': medication.category.name if medication.category else None,
                    'category_id': medication.category_id,
                    'manufacturer': medication.manufacturer.name if medication.manufacturer else None,
                    'manufacturer_id': medication.manufacturer_id,
                    'current_stock': medication.current_stock,
                    'reorder_level': medication.reorder_level,
                    'minimum_stock': medication.minimum_stock,
                    'unit': medication.unit,
                    'unit_price': float(medication.unit_price) if medication.unit_price else 0,
                    'selling_price': float(medication.selling_price) if medication.selling_price else 0,
                    'expiry_date': medication.expiry_date.strftime('%Y-%m-%d') if medication.expiry_date else None,
                    'batch_number': medication.batch_number,
                    'is_active': medication.is_active,
                    'availability': self.get_availability_status(medication),
                    'created_at': medication.created_at,
                    'updated_at': medication.updated_at
                }
            })
        
        # List all medicines with filters
        try:
            from pharmacy.models import Medication
            from django.db.models import F, Q, Sum
        except ImportError:
            return Response({
                'success': False,
                'error': 'Pharmacy module not available'
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        
        medicines = Medication.objects.select_related(
            'category', 'manufacturer'
        ).filter(is_active=True)
        
        # 1. Search filter
        search = request.query_params.get('search')
        if search:
            medicines = medicines.filter(
                Q(name__icontains=search) |
                Q(generic_name__icontains=search) |
                Q(medication_id__icontains=search) |
                Q(batch_number__icontains=search)
            )
        
        # 2. Category filter
        category = request.query_params.get('category')
        if category:
            medicines = medicines.filter(category_id=category)
        
        # 3. Status filter (available, low_stock, out_of_stock)
        status_filter = request.query_params.get('status')
        if status_filter:
            if status_filter == 'AVAILABLE':
                medicines = medicines.filter(current_stock__gt=F('reorder_level'))
            elif status_filter == 'LOW_STOCK':
                medicines = medicines.filter(
                    current_stock__lte=F('reorder_level'),
                    current_stock__gt=0
                )
            elif status_filter == 'OUT_OF_STOCK':
                medicines = medicines.filter(current_stock=0)
        
        # 4. Sorting
        sort_by = request.query_params.get('sort_by', 'name')
        if sort_by == 'name':
            medicines = medicines.order_by('name')
        elif sort_by == '-name':
            medicines = medicines.order_by('-name')
        elif sort_by == 'stock':
            medicines = medicines.order_by('current_stock')
        elif sort_by == '-stock':
            medicines = medicines.order_by('-current_stock')
        
        # 5. Pagination
        page = int(request.query_params.get('page', 1))
        page_size = int(request.query_params.get('page_size', 20))
        total = medicines.count()
        start = (page - 1) * page_size
        end = start + page_size
        paginated_medicines = medicines[start:end]
        
        # Build response data
        medicine_list = []
        for med in paginated_medicines:
            medicine_list.append({
                'id': med.id,
                'medication_id': med.medication_id,
                'name': med.name,
                'generic_name': med.generic_name,
                'category': med.category.name if med.category else 'Uncategorized',
                'category_id': med.category_id,
                'current_stock': med.current_stock,
                'unit': med.unit,
                'reorder_level': med.reorder_level,
                'minimum_stock': med.minimum_stock,
                'selling_price': float(med.selling_price) if med.selling_price else 0,
                'expiry_date': med.expiry_date.strftime('%Y-%m-%d') if med.expiry_date else None,
                'batch_number': med.batch_number,
                'availability': self.get_availability_status(med),
                'status_badge': self.get_status_badge(med),
                'manufacturer': med.manufacturer.name if med.manufacturer else None
            })
        
        # Get summary statistics for the cards
        summary = {
            'available_medicines': medicines.filter(current_stock__gt=F('reorder_level')).count(),
            'low_stock_warnings': medicines.filter(
                current_stock__lte=F('reorder_level'),
                current_stock__gt=0
            ).count(),
            'out_of_stock': medicines.filter(current_stock=0).count(),
            'total_medicines': total
        }
        
        return Response({
            'success': True,
            'data': medicine_list,
            'summary': summary,
            'pagination': {
                'page': page,
                'page_size': page_size,
                'total_pages': (total + page_size - 1) // page_size if page_size > 0 else 1,
                'total': total
            }
        })
    
    def get_availability_status(self, medication):
        """Get availability status of a medicine"""
        if medication.current_stock <= 0:
            return 'Out of Stock'
        elif medication.current_stock <= medication.reorder_level:
            return 'Low Stock'
        else:
            return 'Available'
    
    def get_status_badge(self, medication):
        """Get status badge color"""
        if medication.current_stock <= 0:
            return 'danger'  # Red
        elif medication.current_stock <= medication.reorder_level:
            return 'warning'  # Yellow/Orange
        else:
            return 'success'  # Green


class DoctorMedicineCategoriesView(APIView):
    """
    Get medicine categories with counts
    GET /api/doctor/medicines/categories/
    """
    permission_classes = [IsAuthenticated, IsDoctor]
    
    def get(self, request):
        try:
            from pharmacy.models import MedicationCategory
            from django.db.models import Count
        except ImportError:
            return Response({
                'success': False,
                'error': 'Pharmacy module not available'
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        
        categories = MedicationCategory.objects.filter(is_active=True).annotate(
            medication_count=Count('medications')
        ).order_by('name')
        
        data = []
        for category in categories:
            data.append({
                'id': category.id,
                'name': category.name,
                'description': category.description if hasattr(category, 'description') else None,
                'medication_count': category.medication_count
            })
        
        return Response({
            'success': True,
            'data': data
        })