# apps/appointments/views.py - COMPLETE WORKING VERSION WITH APPOINTMENT MANAGEMENT

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.parsers import JSONParser, FormParser, MultiPartParser
from django.utils import timezone
from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from django.db.models import Count, Q
from datetime import timedelta
from rest_framework.pagination import PageNumberPagination
from django.http import HttpResponse
import qrcode
from io import BytesIO
import json
import base64

from .models import OPTicket, Appointment
from .serializer import (
    OPTicketSerializer, PatientBasicSerializer, DoctorChoiceSerializer,
    AppointmentSerializer, AppointmentListSerializer
)
from .permissions import ReceptionistPermission
from patients.models import PatientProfile
from accounts.models import User
from departments.models import Department


# ========== CONSTANTS FOR APPOINTMENT MANAGEMENT ==========

CANCELLATION_REASONS = [
    ('patient_request', 'Patient Request'),
    ('doctor_unavailable', 'Doctor Unavailable'),
    ('clinic_issue', 'Clinic Issue'),
    ('emergency', 'Emergency'),
    ('no_show', 'No Show'),
    ('other', 'Other'),
]


# ========== CUSTOM PAGINATION FOR RECENT PATIENTS ==========
class RecentPatientsPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


# ========== VIEWSET FOR PATIENTS ==========
class ReceptionistPatientViewSet(viewsets.ModelViewSet):
    permission_classes = [ReceptionistPermission]
    parser_classes = [JSONParser, FormParser, MultiPartParser]
    serializer_class = PatientBasicSerializer
    http_method_names = ['get', 'patch', 'head', 'options']
    
    def get_queryset(self):
        qs = PatientProfile.objects.select_related('user', 'assigned_doctor').order_by('-registered_on')
        search = self.request.query_params.get('search', '')
        stat = self.request.query_params.get('status', '')
        
        if search:
            qs = (
                qs.filter(user__full_name__icontains=search) |
                qs.filter(patient_id__icontains=search) |
                qs.filter(user__email__icontains=search) |
                qs.filter(phone__icontains=search)
            )
        if stat:
            qs = qs.filter(status=stat)
        return qs.distinct()
    
    @action(detail=True, methods=['get'], url_path='tickets')
    def patient_tickets(self, request, pk=None):
        patient = self.get_object()
        tickets = OPTicket.objects.filter(patient=patient).select_related(
            'assigned_doctor', 'department', 'created_by'
        ).order_by('-date', '-token_number')
        serializer = OPTicketSerializer(tickets, many=True, context={'request': request})
        return Response({
            'patient_id': patient.patient_id,
            'count': tickets.count(),
            'tickets': serializer.data,
        })
    
    @action(detail=True, methods=['get'], url_path='history')
    def history(self, request, pk=None):
        patient = self.get_object()
        tickets = OPTicket.objects.filter(patient=patient).select_related(
            'assigned_doctor', 'department', 'created_by'
        ).order_by('-date', '-token_number')
        serializer = OPTicketSerializer(tickets, many=True, context={'request': request})
        return Response({
            'patient': {
                'id': patient.id,
                'patient_id': patient.patient_id,
                'full_name': patient.user.full_name,
                'email': patient.user.email,
                'phone': patient.phone or '',
                'blood_group': patient.blood_group or '',
                'address': patient.address or '',
                'status': patient.status,
                'registered_on': patient.registered_on.isoformat() if patient.registered_on else '',
                'assigned_doctor_name': patient.assigned_doctor.full_name if patient.assigned_doctor else '',
            },
            'total_tickets': tickets.count(),
            'tickets': serializer.data,
        })


# ========== VIEWSET FOR TICKETS ==========
class OPTicketViewSet(viewsets.ModelViewSet):
    permission_classes = [ReceptionistPermission]
    parser_classes = [JSONParser, FormParser, MultiPartParser]
    serializer_class = OPTicketSerializer
    http_method_names = ['get', 'post', 'patch', 'head', 'options']
    
    def get_queryset(self):
        qs = OPTicket.objects.select_related(
            'patient__user', 'assigned_doctor', 'department', 'created_by'
        )
        date = self.request.query_params.get('date', '')
        stat = self.request.query_params.get('status', '')
        dept = self.request.query_params.get('department', '')
        
        if date:
            qs = qs.filter(date=date)
        else:
            qs = qs.filter(date=timezone.now().date())
        if stat:
            qs = qs.filter(status=stat)
        if dept:
            qs = qs.filter(department_id=dept)
        return qs.order_by('token_number')

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx['request'] = self.request
        return ctx
    
    # ========== ADD THIS CREATE METHOD WITH LEAVE CHECK ==========
    def create(self, request, *args, **kwargs):
        """Create OP ticket with doctor leave validation"""
        
        # Check if assigned doctor is on leave today
        assigned_doctor_id = request.data.get('assigned_doctor')
        
        if assigned_doctor_id:
            try:
                from hr.models import LeaveRequest
                from accounts.models import User
                
                doctor = User.objects.get(id=assigned_doctor_id)
                today = timezone.now().date()
                
                # Check if doctor is on approved leave today
                is_on_leave = LeaveRequest.objects.filter(
                    employee=doctor,
                    status='APPROVED',
                    start_date__lte=today,
                    end_date__gte=today
                ).exists()
                
                if is_on_leave:
                    return Response({
                        'error': f'Dr. {doctor.full_name} is on approved leave today. Please assign another doctor.',
                        'doctor_id': doctor.id,
                        'doctor_name': doctor.full_name,
                        'leave_date': str(today)
                    }, status=status.HTTP_400_BAD_REQUEST)
                    
            except ImportError:
                # HR module not installed, skip leave check
                pass
            except User.DoesNotExist:
                pass
        
        # Call the original create method
        return super().create(request, *args, **kwargs)
    
    @action(detail=False, methods=['get'], url_path='today')
    def today(self, request):
        today = timezone.now().date()
        tickets = OPTicket.objects.filter(date=today).select_related(
            'patient__user', 'assigned_doctor', 'department'
        ).order_by('token_number')
        summary = {
            'total': tickets.count(),
            'waiting': tickets.filter(status='WAITING').count(),
            'in_consult': tickets.filter(status='IN_CONSULT').count(),
            'done': tickets.filter(status='DONE').count(),
            'cancelled': tickets.filter(status='CANCELLED').count(),
            'next_token': OPTicket.next_token_for_today(),
        }
        serializer = OPTicketSerializer(tickets, many=True, context={'request': request})
        return Response({
            'date': str(today), 
            'summary': summary, 
            'tickets': serializer.data
        })
    
    @action(detail=True, methods=['patch'], url_path='status')
    def update_status(self, request, pk=None):
        ticket = self.get_object()
        new_status = request.data.get('status')
        if new_status not in dict(OPTicket.STATUS_CHOICES):
            return Response({'detail': 'Invalid status'}, status=400)
        ticket.status = new_status
        ticket.save()
        return Response(OPTicketSerializer(ticket, context={'request': request}).data)
    
    @action(detail=False, methods=['get'], url_path='doctors')
    def doctors(self, request):
        doctors = User.objects.filter(
            role__in=['END', 'GYN', 'ANE'], is_active=True
        ).order_by('full_name')
        return Response(DoctorChoiceSerializer(doctors, many=True).data)
    
    @action(detail=False, methods=['get'], url_path='departments')
    def departments(self, request):
        depts = Department.objects.filter(is_active=True)
        
        # Add parameter filtering for consultation departments
        dept_type = request.query_params.get('type', '')
        
        if dept_type == 'consultation':
            consultation_departments = ['Gynaecology', 'Department of Advanced Reproduction', 'Andrology']
            depts = depts.filter(name__in=consultation_departments)
        
        # Optional: Add more filters if needed
        elif dept_type == 'lab':
            lab_departments = ['Embryology & IVF Lab', 'Laboratory(General)']
            depts = depts.filter(name__in=lab_departments)
        
        elif dept_type == 'pharmacy':
            depts = depts.filter(name='Pharmacy')
        
        elif dept_type == 'support':
            support_departments = ['Reception & Front Desk', 'Nursing', 'Clinical Counselling', 'Financial Counselling']
            depts = depts.filter(name__in=support_departments)
        
        elif dept_type == 'admin':
            admin_departments = ['Administration & Management', 'HR & Payroll']
            depts = depts.filter(name__in=admin_departments)
        
        # Return as list of values
        return Response(list(depts.values('id', 'name', 'code')))
    
    # ========== QR CODE ENDPOINTS ==========
    @action(detail=True, methods=['get'], url_path='qrcode')
    def get_qr_code_image(self, request, pk=None):
        """Generate and return QR code as PNG image for a ticket."""
        ticket = self.get_object()
        
        if ticket.status == 'CANCELLED':
            return Response({'error': 'Cannot generate QR code for cancelled ticket'}, status=400)
        
        frontend_url = self.request.build_absolute_uri('/').rstrip('/')
        qr_data = {
            'ticket_id': ticket.id,
            'token_number': ticket.token_number,
            'patient_name': ticket.patient.user.full_name,
            'patient_id': ticket.patient.patient_id,
            'doctor_name': ticket.assigned_doctor.full_name if ticket.assigned_doctor else '',
            'date': str(ticket.date),
            'status': ticket.status,
            'verify_url': f"{frontend_url}/verify-ticket/{ticket.id}"
        }
        
        qr_string = json.dumps(qr_data)
        qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_L, box_size=10, border=4)
        qr.add_data(qr_string)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        
        response = HttpResponse(content_type="image/png")
        img.save(response, "PNG")
        return response
    
    @action(detail=True, methods=['get'], url_path='qrcode-base64')
    def get_qr_code_base64(self, request, pk=None):
        """Generate and return QR code as base64 string for a ticket."""
        ticket = self.get_object()
        
        if ticket.status == 'CANCELLED':
            return Response({'error': 'Cannot generate QR code for cancelled ticket'}, status=400)
        
        frontend_url = self.request.build_absolute_uri('/').rstrip('/')
        qr_data = {
            'ticket_id': ticket.id,
            'token_number': ticket.token_number,
            'patient_name': ticket.patient.user.full_name,
            'patient_id': ticket.patient.patient_id,
            'doctor_name': ticket.assigned_doctor.full_name if ticket.assigned_doctor else '',
            'date': str(ticket.date),
            'status': ticket.status,
            'verify_url': f"{frontend_url}/verify-ticket/{ticket.id}"
        }
        
        qr_string = json.dumps(qr_data)
        qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_L, box_size=10, border=4)
        qr.add_data(qr_string)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        
        buffer = BytesIO()
        img.save(buffer, format="PNG")
        img_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
        
        return Response({
            'ticket_id': ticket.id,
            'token_number': ticket.token_number,
            'qr_code': f"data:image/png;base64,{img_base64}"
        })
# ========== APPOINTMENT MANAGEMENT APIS ==========

# 1. BOOK APPOINTMENT API
class BookAppointmentView(APIView):
    """
    Book a new appointment
    POST /api/receptionist/appointments/book/
    
    Request Body:
    {
        "patient_id": 12,
        "doctor_id": 33,
        "appointment_date": "2026-06-10",
        "time_slot": "10:00 AM",
        "visit_reason": "CONSULTATION",
        "notes": "Optional notes"
    }
    """
    permission_classes = [ReceptionistPermission]
    
    def post(self, request):
        serializer = AppointmentSerializer(data=request.data, context={'request': request})
        
        if serializer.is_valid():
            doctor = serializer.validated_data.get('doctor')
            appointment_date = serializer.validated_data.get('appointment_date')
            time_slot = serializer.validated_data.get('time_slot')
            
            # ========== CHECK IF DOCTOR IS ON LEAVE ==========
            try:
                from hr.models import LeaveRequest
                
                # Check if doctor has approved leave on this date
                is_on_leave = LeaveRequest.objects.filter(
                    employee=doctor,
                    status='APPROVED',
                    start_date__lte=appointment_date,
                    end_date__gte=appointment_date
                ).exists()
                
                if is_on_leave:
                    return Response({
                        'error': f'Dr. {doctor.full_name} is on approved leave on {appointment_date}. Please select another date or doctor.',
                        'doctor_id': doctor.id,
                        'doctor_name': doctor.full_name,
                        'leave_date': str(appointment_date)
                    }, status=status.HTTP_400_BAD_REQUEST)
                    
            except ImportError:
                # HR module not installed, skip leave check
                pass
            
            # ========== CHECK TIME SLOT AVAILABILITY ==========
            if doctor and appointment_date and time_slot:
                available_slots = Appointment.get_available_time_slots(
                    doctor.id,
                    appointment_date
                )
                
                if time_slot not in available_slots:
                    return Response({
                        'error': f'Time slot {time_slot} is not available',
                        'available_slots': available_slots
                    }, status=status.HTTP_400_BAD_REQUEST)
            
            # ========== CREATE APPOINTMENT ==========
            appointment = serializer.save()
            
            return Response({
                'success': True,
                'message': 'Appointment booked successfully',
                'appointment': AppointmentSerializer(appointment, context={'request': request}).data
            }, status=status.HTTP_201_CREATED)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

# 2. SEARCH APPOINTMENT API
class SearchAppointmentView(APIView):
    """
    Search appointments by ID, patient name, or MRN
    GET /api/receptionist/appointments/search/?q=john
    GET /api/receptionist/appointments/search/?appointment_id=APT-20260001
    GET /api/receptionist/appointments/search/?patient_mrn=PAT012
    """
    permission_classes = [ReceptionistPermission]
    
    def get(self, request):
        query = request.query_params.get('q', '')
        appointment_id = request.query_params.get('appointment_id', '')
        patient_mrn = request.query_params.get('patient_mrn', '')
        
        if appointment_id:
            try:
                appointment = Appointment.objects.get(appointment_id=appointment_id)
                serializer = AppointmentSerializer(appointment, context={'request': request})
                return Response({
                    'success': True,
                    'appointment': serializer.data
                })
            except Appointment.DoesNotExist:
                return Response({'error': 'Appointment not found'}, status=404)
        
        if patient_mrn:
            try:
                patient = PatientProfile.objects.get(patient_id=patient_mrn)
                appointments = Appointment.objects.filter(patient=patient).order_by('-appointment_date')
                serializer = AppointmentSerializer(appointments, many=True, context={'request': request})
                return Response({
                    'success': True,
                    'count': appointments.count(),
                    'appointments': serializer.data
                })
            except PatientProfile.DoesNotExist:
                return Response({'error': 'Patient not found'}, status=404)
        
        if query:
            appointments = Appointment.objects.filter(
                Q(patient__user__full_name__icontains=query) |
                Q(appointment_id__icontains=query) |
                Q(patient__patient_id__icontains=query)
            ).select_related('patient__user', 'doctor', 'department')[:20]
            
            serializer = AppointmentSerializer(appointments, many=True, context={'request': request})
            return Response({
                'success': True,
                'count': appointments.count(),
                'appointments': serializer.data
            })
        
        return Response({'error': 'Please provide search query, appointment ID, or patient MRN'}, status=400)


# 3. RESCHEDULE APPOINTMENT API
class RescheduleAppointmentView(APIView):
    """
    Reschedule an existing appointment
    PATCH /api/receptionist/appointments/reschedule/{appointment_id}/
    
    Request Body:
    {
        "new_date": "2026-06-15",
        "new_time_slot": "02:00 PM",
        "reason": "Patient requested"
    }
    """
    permission_classes = [ReceptionistPermission]
    
    def patch(self, request, appointment_id):
        appointment = get_object_or_404(Appointment, id=appointment_id)
        
        if appointment.status in ['COMPLETED', 'CANCELLED', 'NO_SHOW']:
            return Response({
                'error': f'Cannot reschedule a {appointment.get_status_display()} appointment'
            }, status=400)
        
        new_date_str = request.data.get('new_date')
        new_time_slot = request.data.get('new_time_slot')
        reason = request.data.get('reason', '')
        
        if not new_date_str:
            return Response({'error': 'new_date is required'}, status=400)
        
        try:
            new_date = timezone.datetime.strptime(new_date_str, '%Y-%m-%d').date()
        except ValueError:
            return Response({'error': 'Invalid date format. Use YYYY-MM-DD'}, status=400)
        
        # Check if new date is not in the past
        if new_date < timezone.now().date():
            return Response({'error': 'Cannot reschedule to a past date'}, status=400)
        
        # Check availability for new slot
        if appointment.doctor and new_time_slot:
            available_slots = Appointment.get_available_time_slots(
                appointment.doctor.id,
                new_date
            )
            if new_time_slot not in available_slots:
                return Response({
                    'error': f'Time slot {new_time_slot} is not available',
                    'available_slots': available_slots
                }, status=400)
        
        # Store old data
        old_data = {
            'date': appointment.appointment_date.isoformat(),
            'time_slot': appointment.time_slot,
            'token_number': appointment.token_number,
            'status': appointment.status,
            'status_display': appointment.get_status_display()
        }
        
        # ========== RESCHEDULE THE APPOINTMENT (Direct update) ==========
        # Update date and time
        appointment.appointment_date = new_date
        if new_time_slot:
            appointment.time_slot = new_time_slot
        
        # Update status to RESCHEDULED
        if appointment.status != 'RESCHEDULED':
            appointment.status = 'RESCHEDULED'
        
        # Update token number for the new date if it's today
        if new_date == timezone.now().date():
            last_token = Appointment.objects.filter(
                appointment_date=new_date
            ).order_by('-token_number').first()
            appointment.token_number = (last_token.token_number + 1) if last_token else 1
        
        # Add reschedule reason to notes
        timestamp = timezone.now().strftime('%Y-%m-%d %H:%M:%S')
        if reason:
            reschedule_note = f"\n[RESCHEDULED at {timestamp}] From {old_data['date']} at {old_data['time_slot']} to {new_date} at {new_time_slot or appointment.time_slot}. Reason: {reason}"
        else:
            reschedule_note = f"\n[RESCHEDULED at {timestamp}] From {old_data['date']} at {old_data['time_slot']} to {new_date} at {new_time_slot or appointment.time_slot}"
        
        appointment.notes = (appointment.notes or '') + reschedule_note
        
        # Increment reschedule count
        
        
        appointment.save()
        # ========== END OF RESCHEDULE LOGIC ==========
        
        # Regenerate QR code
        appointment.generate_qr_code(request)
        appointment.save()
        
        return Response({
            'success': True,
            'message': 'Appointment rescheduled successfully',
            'old_appointment': old_data,
            'new_appointment': {
                'id': appointment.id,
                'appointment_id': appointment.appointment_id,
                'token_number': appointment.token_number,
                'patient': {
                    'id': appointment.patient.id,
                    'name': appointment.patient.user.full_name,
                    'mrn': appointment.patient.patient_id,
                    'phone': appointment.patient.phone,
                    'email': appointment.patient.user.email
                },
                'doctor': {
                    'id': appointment.doctor.id if appointment.doctor else None,
                    'name': appointment.doctor.full_name if appointment.doctor else None,
                    'specialization': appointment.doctor.get_role_display() if appointment.doctor else None,
                } if appointment.doctor else None,
                'appointment_date': appointment.appointment_date.isoformat(),
                'time_slot': appointment.time_slot,
                'status': appointment.status,
                'status_display': appointment.get_status_display(),
                'rescheduled_count': appointment.rescheduled_count,
                'rescheduled_from': appointment.rescheduled_from,
                'notes': appointment.notes,
                'qr_code_base64': appointment.qr_code if hasattr(appointment, 'qr_code') else None
            }
        })
# 4. CANCEL APPOINTMENT API
class CancelAppointmentView(APIView):
    """
    Cancel an appointment
    PATCH /api/receptionist/appointments/cancel/{appointment_id}/
    
    Request Body:
    {
        "reason": "patient_request",
        "notes": "Patient called to cancel"
    }
    """
    permission_classes = [ReceptionistPermission]
    
    def patch(self, request, appointment_id):
        appointment = get_object_or_404(Appointment, id=appointment_id)
        
        if appointment.status in ['COMPLETED', 'CANCELLED', 'NO_SHOW']:
            return Response({
                'error': f'Cannot cancel a {appointment.get_status_display()} appointment'
            }, status=400)
        
        cancellation_reason = request.data.get('reason', 'patient_request')
        cancellation_notes = request.data.get('notes', '')
        
        # Get display reason
        reason_display = dict(CANCELLATION_REASONS).get(cancellation_reason, cancellation_reason)
        
        # Cancel the appointment
        appointment.cancel(reason=reason_display)
        
        # Add cancellation notes
        if cancellation_notes:
            appointment.notes = f"{appointment.notes}\n[CANCELLATION NOTES: {cancellation_notes}]"
            appointment.save()
        
        return Response({
            'success': True,
            'message': 'Appointment cancelled successfully',
            'cancelled_appointment': {
                'id': appointment.id,
                'appointment_id': appointment.appointment_id,
                'patient_name': appointment.patient.user.full_name,
                'doctor_name': appointment.doctor.full_name if appointment.doctor else None,
                'date': appointment.appointment_date,
                'time_slot': appointment.time_slot,
                'cancelled_at': appointment.cancelled_at,
                'cancellation_reason': appointment.cancellation_reason
            }
        })


# 5. DOCTOR-WISE APPOINTMENT CALENDAR API
# apps/appointments/views.py - Update DoctorAppointmentCalendarView

class DoctorAppointmentCalendarView(APIView):
    """
    Get doctor-wise appointment calendar with leaves
    GET /api/receptionist/appointments/calendar/
    GET /api/receptionist/appointments/calendar/?doctor_id=33&start_date=2026-06-01&end_date=2026-06-07
    """
    permission_classes = [ReceptionistPermission]
    
    def get(self, request, doctor_id=None):
        # Get date range
        start_date_str = request.query_params.get('start_date')
        end_date_str = request.query_params.get('end_date')
        
        if not start_date_str:
            start_date = timezone.now().date()
        else:
            start_date = timezone.datetime.strptime(start_date_str, '%Y-%m-%d').date()
        
        if not end_date_str:
            end_date = start_date + timedelta(days=7)
        else:
            end_date = timezone.datetime.strptime(end_date_str, '%Y-%m-%d').date()
        
        # Filter by doctor
        if doctor_id:
            doctors = User.objects.filter(id=doctor_id, role__in=['END', 'GYN', 'ANE'], is_active=True)
        else:
            doctors = User.objects.filter(role__in=['END', 'GYN', 'ANE'], is_active=True)
        
        # Time slots for calendar
        time_slots = [
            '09:00 AM', '09:30 AM', '10:00 AM', '10:30 AM',
            '11:00 AM', '11:30 AM', '12:00 PM', '12:30 PM',
            '02:00 PM', '02:30 PM', '03:00 PM', '03:30 PM',
            '04:00 PM', '04:30 PM'
        ]
        
        calendar_data = []
        
        for doctor in doctors:
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
                
                # Create time slots for this day
                slots = []
                for slot in time_slots:
                    appointment_for_slot = day_appointments.filter(time_slot=slot).first()
                    
                    if is_leave_date:
                        # Show as leave day (unavailable)
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
                                'id': appointment_for_slot.id if appointment_for_slot else None,
                                'appointment_id': appointment_for_slot.appointment_id if appointment_for_slot else None,
                                'token': appointment_for_slot.token_number if appointment_for_slot else None,
                                'patient_name': appointment_for_slot.patient.user.full_name if appointment_for_slot else None,
                                'patient_mrn': appointment_for_slot.patient.patient_id if appointment_for_slot else None,
                                'status': appointment_for_slot.status if appointment_for_slot else None,
                                'status_display': appointment_for_slot.get_status_display() if appointment_for_slot else None,
                            } if appointment_for_slot else None,
                            'available': appointment_for_slot is None,
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
            
            calendar_data.append({
                'doctor_id': doctor.id,
                'doctor_name': doctor.full_name,
                'specialization': doctor.get_role_display(),
                'room_number': getattr(doctor, 'room_number', 'Not assigned'),
                'calendar_view': calendar_view,
                'total_appointments': appointments.count(),
                'total_leave_days': len(approved_leaves)
            })
        
        return Response({
            'success': True,
            'start_date': str(start_date),
            'end_date': str(end_date),
            'calendar': calendar_data
        })


# 6. DAILY APPOINTMENT LIST API
class DailyAppointmentListView(APIView):
    """
    Get daily appointment list with filters
    GET /api/receptionist/appointments/daily/
    GET /api/receptionist/appointments/daily/?date=2026-06-03&status=CONFIRMED&search=john
    """
    permission_classes = [ReceptionistPermission]
    
    def get(self, request):
        date_str = request.query_params.get('date', str(timezone.now().date()))
        status_filter = request.query_params.get('status', '')
        search = request.query_params.get('search', '')
        
        # Parse date
        try:
            date = timezone.datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            return Response({'error': 'Invalid date format. Use YYYY-MM-DD'}, status=400)
        
        # Base queryset
        appointments = Appointment.objects.filter(
            appointment_date=date
        ).select_related(
            'patient__user', 'doctor', 'department'
        ).order_by('appointment_time', 'token_number')
        
        # Apply status filter
        if status_filter and status_filter != 'ALL':
            appointments = appointments.filter(status=status_filter)
        
        # Apply search filter
        if search:
            appointments = appointments.filter(
                Q(patient__user__full_name__icontains=search) |
                Q(patient__patient_id__icontains=search) |
                Q(appointment_id__icontains=search)
            )
        
        # Summary statistics
        summary = {
            'total': appointments.count(),
            'scheduled': appointments.filter(status='SCHEDULED').count(),
            'confirmed': appointments.filter(status='CONFIRMED').count(),
            'in_progress': appointments.filter(status='IN_PROGRESS').count(),
            'completed': appointments.filter(status='COMPLETED').count(),
            'cancelled': appointments.filter(status='CANCELLED').count(),
            'no_show': appointments.filter(status='NO_SHOW').count(),
            'rescheduled': appointments.filter(status='RESCHEDULED').count()
        }
        
        # Legend for status
        legend = {
            'scheduled': {'status': 'SCHEDULED', 'color': '#FFA500', 'display': 'Scheduled'},
            'confirmed': {'status': 'CONFIRMED', 'color': '#2196F3', 'display': 'Confirmed'},
            'in_progress': {'status': 'IN_PROGRESS', 'color': '#FF9800', 'display': 'In Progress'},
            'completed': {'status': 'COMPLETED', 'color': '#4CAF50', 'display': 'Completed'},
            'cancelled': {'status': 'CANCELLED', 'color': '#F44336', 'display': 'Cancelled'},
            'no_show': {'status': 'NO_SHOW', 'color': '#9E9E9E', 'display': 'No Show'},
            'rescheduled': {'status': 'RESCHEDULED', 'color': '#9C27B0', 'display': 'Rescheduled'}
        }
        
        # Use list serializer for better performance
        serializer = AppointmentListSerializer(appointments, many=True, context={'request': request})
        
        return Response({
            'success': True,
            'date': str(date),
            'day_name': date.strftime('%A'),
            'summary': summary,
            'appointments': serializer.data,
            'legend': legend,
            'total_count': appointments.count()
        })


# 7. WALK-IN PATIENT REGISTRATION API
class WalkInRegistrationView(APIView):
    """
    Register a walk-in patient and create immediate appointment
    POST /api/receptionist/appointments/walkin/
    
    Request Body:
    {
        "patient": {
            "full_name": "John Doe",
            "phone": "9876543210",
            "gender": "MALE",
            "age": 30
        },
        "appointment": {
            "doctor_id": 33,
            "visit_reason": "CONSULTATION",
            "payment_status": true
        }
    }
    """
    permission_classes = [ReceptionistPermission]
    
    def post(self, request):
        data = request.data
        
        # Validate required fields
        if 'patient' not in data:
            return Response({'error': 'Patient information required'}, status=400)
        
        patient_data = data.get('patient', {})
        required_fields = ['full_name', 'phone']
        for field in required_fields:
            if field not in patient_data:
                return Response({'error': f'Patient {field} is required'}, status=400)
        
        # Create user account for patient
        username = f"walkin_{int(timezone.now().timestamp())}_{patient_data.get('phone', '')[:8]}"
        email = patient_data.get('email', f"{username}@walkin.local")
        
        user = User.objects.create_user(
            username=username,
            email=email,
            full_name=patient_data.get('full_name'),
            role='PAT',
            is_active=True
        )
        
        # Calculate date of birth from age
        date_of_birth = None
        age = patient_data.get('age')
        if age:
            from datetime import date
            try:
                age_int = int(age)
                date_of_birth = date.today().replace(year=date.today().year - age_int)
            except:
                pass
        elif patient_data.get('date_of_birth'):
            date_of_birth = patient_data.get('date_of_birth')
        
        # Create patient profile
        patient = PatientProfile.objects.create(
            user=user,
            phone=patient_data.get('phone'),
            date_of_birth=date_of_birth,
            gender=patient_data.get('gender', 'NOT_SPECIFIED'),
            address=patient_data.get('address', ''),
            status='ACTIVE',
            registered_on=timezone.now()
        )
        
        # Get appointment data
        appointment_data = data.get('appointment', {})
        
        # Get doctor (if specified, otherwise assign first available)
        doctor_id = appointment_data.get('doctor_id')
        if doctor_id:
            doctor = get_object_or_404(User, id=doctor_id, role__in=['END', 'GYN', 'ANE'])
        else:
            doctor = User.objects.filter(role__in=['END', 'GYN', 'ANE'], is_active=True).first()
            if not doctor:
                return Response({'error': 'No doctors available'}, status=400)
        
        # Create appointment
        appointment = Appointment.objects.create(
            patient=patient,
            doctor=doctor,
            appointment_date=timezone.now().date(),
            appointment_type='WALK_IN',
            status='CONFIRMED',
            visit_reason=appointment_data.get('visit_reason', 'CONSULTATION'),
            notes=f"Walk-in patient registered on {timezone.now().strftime('%Y-%m-%d %H:%M')}. {appointment_data.get('notes', '')}",
            created_by=request.user,
            payment_status=appointment_data.get('payment_status', False),
            payment_amount=appointment_data.get('payment_amount', None)
        )
        
        # Generate QR code
        appointment.generate_qr_code(request)
        appointment.save()
        
        # Create OP Ticket for walk-in
        op_ticket = OPTicket.objects.create(
            patient=patient,
            assigned_doctor=doctor,
            visit_reason=appointment.visit_reason,
            notes=f"Walk-in patient - Appointment ID: {appointment.appointment_id}",
            created_by=request.user,
            status='WAITING',
            payment_done=appointment.payment_status
        )
        
        serializer = AppointmentSerializer(appointment, context={'request': request})
        
        return Response({
            'success': True,
            'message': 'Walk-in patient registered successfully',
            'patient': {
                'id': patient.id,
                'patient_id': patient.patient_id,
                'full_name': patient.user.full_name,
                'phone': patient.phone,
                'age': age,
                'gender': patient.gender
            },
            'appointment': serializer.data,
            'op_ticket_id': op_ticket.id,
            'token_number': op_ticket.token_number
        }, status=201)


# 8. APPOINTMENT DETAILS API
class AppointmentDetailView(APIView):
    """
    Get detailed appointment information
    GET /api/receptionist/appointments/{appointment_id}/detail/
    """
    permission_classes = [ReceptionistPermission]
    
    def get(self, request, appointment_id):
        appointment = get_object_or_404(Appointment, id=appointment_id)
        
        # Get related OP ticket if exists
        op_ticket = OPTicket.objects.filter(
            patient=appointment.patient,
            date=appointment.appointment_date
        ).first()
        
        appointment_details = {
            'appointment': AppointmentSerializer(appointment, context={'request': request}).data,
            'patient_details': {
                'id': appointment.patient.id,
                'mrn': appointment.patient.patient_id,
                'full_name': appointment.patient.user.full_name,
                'email': appointment.patient.user.email,
                'phone': appointment.patient.phone,
                'date_of_birth': appointment.patient.date_of_birth,
                'gender': appointment.patient.gender,
                'blood_group': appointment.patient.blood_group,
                'address': appointment.patient.address,
                'total_visits': OPTicket.objects.filter(patient=appointment.patient).count(),
                'total_appointments': Appointment.objects.filter(patient=appointment.patient).count()
            },
            'doctor_details': {
                'id': appointment.doctor.id if appointment.doctor else None,
                'name': appointment.doctor.full_name if appointment.doctor else None,
                'specialization': appointment.doctor.get_role_display() if appointment.doctor else None,
            } if appointment.doctor else None,
            'associated_op_ticket': {
                'id': op_ticket.id,
                'token_number': op_ticket.token_number,
                'status': op_ticket.status
            } if op_ticket else None,
            'can_reschedule': appointment.status not in ['COMPLETED', 'CANCELLED', 'NO_SHOW'],
            'can_cancel': appointment.status not in ['COMPLETED', 'CANCELLED', 'NO_SHOW'],
        }
        
        return Response({
            'success': True,
            'details': appointment_details
        })


# 9. AVAILABLE TIME SLOTS API
class AvailableTimeSlotsView(APIView):
    """
    Get available time slots for a doctor on a specific date
    GET /api/receptionist/appointments/available-slots/?doctor_id=33&date=2026-06-10
    """
    permission_classes = [ReceptionistPermission]
    
    def get(self, request):
        doctor_id = request.query_params.get('doctor_id')
        date_str = request.query_params.get('date')
        
        if not doctor_id or not date_str:
            return Response({'error': 'doctor_id and date are required'}, status=400)
        
        doctor = get_object_or_404(User, id=doctor_id, role__in=['END', 'GYN', 'ANE'])
        
        try:
            date = timezone.datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            return Response({'error': 'Invalid date format. Use YYYY-MM-DD'}, status=400)
        
        # Get available slots
        available_slots = Appointment.get_available_time_slots(doctor_id, date)
        
        # Get existing appointments for this doctor on this date
        existing_appointments = Appointment.objects.filter(
            doctor=doctor,
            appointment_date=date,
            status__in=['SCHEDULED', 'CONFIRMED', 'IN_PROGRESS']
        ).order_by('appointment_time')
        
        # Prepare booked slots details
        booked_slots = []
        for apt in existing_appointments:
            booked_slots.append({
                'time_slot': apt.time_slot,
                'appointment_id': apt.appointment_id,
                'patient_name': apt.patient.user.full_name,
                'status': apt.status
            })
        
        all_time_slots = [
            {'slot': '09:00 AM', 'time': '09:00', 'available': '09:00 AM' in available_slots},
            {'slot': '09:30 AM', 'time': '09:30', 'available': '09:30 AM' in available_slots},
            {'slot': '10:00 AM', 'time': '10:00', 'available': '10:00 AM' in available_slots},
            {'slot': '10:30 AM', 'time': '10:30', 'available': '10:30 AM' in available_slots},
            {'slot': '11:00 AM', 'time': '11:00', 'available': '11:00 AM' in available_slots},
            {'slot': '11:30 AM', 'time': '11:30', 'available': '11:30 AM' in available_slots},
            {'slot': '12:00 PM', 'time': '12:00', 'available': '12:00 PM' in available_slots},
            {'slot': '12:30 PM', 'time': '12:30', 'available': '12:30 PM' in available_slots},
            {'slot': '02:00 PM', 'time': '14:00', 'available': '02:00 PM' in available_slots},
            {'slot': '02:30 PM', 'time': '14:30', 'available': '02:30 PM' in available_slots},
            {'slot': '03:00 PM', 'time': '15:00', 'available': '03:00 PM' in available_slots},
            {'slot': '03:30 PM', 'time': '15:30', 'available': '03:30 PM' in available_slots},
            {'slot': '04:00 PM', 'time': '16:00', 'available': '04:00 PM' in available_slots},
            {'slot': '04:30 PM', 'time': '16:30', 'available': '04:30 PM' in available_slots},
        ]
        
        return Response({
            'success': True,
            'doctor_id': doctor.id,
            'doctor_name': doctor.full_name,
            'date': str(date),
            'total_slots': len(all_time_slots),
            'booked_slots_count': len(booked_slots),
            'available_slots_count': len(available_slots),
            'all_slots': all_time_slots,
            'available_slots': available_slots,
            'booked_slots_details': booked_slots
        })


# ========== SEPARATE API FOR RECENT PATIENTS (WITH PAGINATION) ==========
class RecentPatientsView(APIView):
    """
    Separate API endpoint for recent patients with pagination.
    This prevents the dashboard from loading all patients at once.
    
    Query Parameters:
    - page: Page number (default: 1)
    - page_size: Items per page (default: 20, max: 100)
    - search: Search by name, MRN, or phone
    - status: Filter by patient status
    """
    permission_classes = [ReceptionistPermission]
    pagination_class = RecentPatientsPagination
    
    def get(self, request):
        # Get query parameters
        search = request.query_params.get('search', '')
        status_filter = request.query_params.get('status', '')
        page = int(request.query_params.get('page', 1))
        page_size = min(int(request.query_params.get('page_size', 20)), 100)
        
        # Base queryset
        patients = PatientProfile.objects.select_related(
            'user', 'assigned_doctor'
        ).order_by('-registered_on')
        
        # Apply search filter
        if search:
            patients = patients.filter(
                Q(user__full_name__icontains=search) |
                Q(patient_id__icontains=search) |
                Q(phone__icontains=search) |
                Q(user__email__icontains=search)
            )
        
        # Apply status filter
        if status_filter:
            patients = patients.filter(status=status_filter)
        
        # Get total count before pagination
        total_count = patients.count()
        
        # Apply pagination
        start = (page - 1) * page_size
        end = start + page_size
        paginated_patients = patients[start:end]
        
        # Format response
        recent_patients_list = []
        for patient in paginated_patients:
            # Get last visit date (most recent ticket)
            last_ticket = OPTicket.objects.filter(patient=patient).order_by('-date', '-created_at').first()
            
            recent_patients_list.append({
                "id": patient.id,
                "name": patient.user.full_name,
                "mrn": patient.patient_id,
                "last_visit": last_ticket.date.isoformat() if last_ticket and last_ticket.date else 
                             patient.registered_on.isoformat() if patient.registered_on else None,
                "doctor": patient.assigned_doctor.full_name if patient.assigned_doctor else "Not Assigned",
                "status": patient.status,
                "status_display": patient.get_status_display(),
                "phone": patient.phone or "",
                "email": patient.user.email or "",
                "registered_on": patient.registered_on.isoformat() if patient.registered_on else None,
                "total_visits": OPTicket.objects.filter(patient=patient).count()
            })
        
        # Return paginated response
        return Response({
            "success": True,
            "data": recent_patients_list,
            "pagination": {
                "current_page": page,
                "page_size": page_size,
                "total_count": total_count,
                "total_pages": (total_count + page_size - 1) // page_size,
                "has_next": end < total_count,
                "has_previous": page > 1
            },
            "filters": {
                "search": search,
                "status": status_filter
            }
        })



# ========== DASHBOARD VIEW WITH DATE FILTERS (CORRECTED) ==========
class ReceptionistDashboardView(APIView):
    permission_classes = [ReceptionistPermission]

    def get(self, request):
        # ========== GET DATE RANGE FROM QUERY PARAMETERS ==========
        date_range = request.query_params.get('range', 'daily')  # daily, weekly, monthly, custom
        start_date_str = request.query_params.get('start_date')
        end_date_str = request.query_params.get('end_date')
        
        today = timezone.now().date()
        current_time = timezone.now()
        
        # Calculate date range based on filter
        if date_range == 'daily':
            start_date = today
            end_date = today
            range_label = "Today"
        elif date_range == 'weekly':
            start_date = today - timedelta(days=today.weekday())
            end_date = today
            range_label = "This Week"
        elif date_range == 'monthly':
            start_date = today.replace(day=1)
            end_date = today
            range_label = "This Month"
        elif date_range == 'custom' and start_date_str and end_date_str:
            try:
                start_date = timezone.datetime.strptime(start_date_str, '%Y-%m-%d').date()
                end_date = timezone.datetime.strptime(end_date_str, '%Y-%m-%d').date()
                range_label = f"{start_date_str} to {end_date_str}"
            except ValueError:
                start_date = today
                end_date = today
                range_label = "Today"
        else:
            start_date = today
            end_date = today
            range_label = "Today"
        
        weekdays = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        
        # ========== FILTER TICKETS AND APPOINTMENTS BY DATE RANGE ==========
        filtered_tickets = OPTicket.objects.filter(
            date__gte=start_date,
            date__lte=end_date
        ).select_related('patient__user', 'assigned_doctor', 'department', 'created_by')
        
        filtered_appointments = Appointment.objects.filter(
            appointment_date__gte=start_date,
            appointment_date__lte=end_date
        )
        
        user = request.user
        
        # ========== 1. Receptionist Info ==========
        receptionist_info = {
            "id": user.id,
            "name": user.full_name,
            "role": "Receptionist",
            "profile_image": None,
            "employee_id": f"REC{user.id:04d}",
            "shift": "Morning (9:00 AM - 5:00 PM)",
            "join_date": user.date_joined.date().isoformat() if user.date_joined else "2024-01-01"
        }
        
        # ========== 2. Clinic Info ==========
        clinic_info = {
            "name": "IVF Speciality Clinic",
            "location": "Kochi, Kerala",
            "contact": "+91 484 1234567",
            "working_hours": "9:00 AM - 6:00 PM",
            "current_time": current_time.isoformat(),
            "current_date": f"{weekdays[current_time.weekday()]}, {current_time.strftime('%d %B %Y')}",
            "date_range": range_label,
            "start_date": str(start_date),
            "end_date": str(end_date)
        }
        
        # ========== 3. Stats for Date Range ==========
        todays_stats = {
            "patients_registered": PatientProfile.objects.filter(
                registered_on__gte=start_date,
                registered_on__lte=end_date
            ).count(),
            "tickets_generated": filtered_tickets.count(),
            "walkin_patients": filtered_appointments.filter(appointment_type='WALK_IN').count(),
            "appointments_scheduled": filtered_appointments.count(),
            "appointments_completed": filtered_tickets.filter(status='DONE').count(),
            "appointments_missed": filtered_appointments.filter(status='NO_SHOW').count(),
            "appointments_cancelled": filtered_tickets.filter(status='CANCELLED').count(),
            "revenue_collected": 0.00,
            "pending_payments": 0.00,
            "insurance_claims": 0
        }
        
        # ========== 4. Queue Stats ==========
        if date_range == 'daily':
            queue_stats = {
                "total_waiting": filtered_tickets.filter(status='WAITING').count(),
                "in_consultation": filtered_tickets.filter(status='IN_CONSULT').count(),
                "completed": filtered_tickets.filter(status='DONE').count(),
                "cancelled": filtered_tickets.filter(status='CANCELLED').count(),
                "no_shows": filtered_appointments.filter(status='NO_SHOW').count(),
                "next_token": OPTicket.next_token_for_today(),
                "current_serving": self.get_current_serving_token(filtered_tickets),
                "average_wait_time": self.calculate_average_wait_time(filtered_tickets),
                "peak_hour": self.get_peak_hour(filtered_tickets),
                "queue_status": "active" if filtered_tickets.exists() else "inactive"
            }
        else:
            queue_stats = {
                "total_waiting": 0,
                "in_consultation": 0,
                "completed": filtered_tickets.filter(status='DONE').count(),
                "cancelled": filtered_tickets.filter(status='CANCELLED').count(),
                "no_shows": filtered_appointments.filter(status='NO_SHOW').count(),
                "next_token": 0,
                "current_serving": 0,
                "average_wait_time": self.calculate_average_wait_time(filtered_tickets),
                "peak_hour": self.get_peak_hour(filtered_tickets),
                "queue_status": "historical"
            }
        
        # ========== 5. Patient Metrics ==========
        patient_metrics = {
            "total_patients": PatientProfile.objects.count(),
            "new_patients_in_range": PatientProfile.objects.filter(
                registered_on__gte=start_date,
                registered_on__lte=end_date
            ).count(),
            "returning_patients": self.get_returning_patients_count_range(start_date, end_date),
            "active_treatments": PatientProfile.objects.filter(status='ACTIVE').count(),
            "completed_treatments": PatientProfile.objects.filter(status='COMPLETED').count(),
            "patient_satisfaction_rate": 4.8,
            "ratings_count": 258
        }
        
        # ========== 6. Date Range Queue ==========
        date_range_queue = []
        for ticket in filtered_tickets.filter(status__in=['WAITING', 'IN_CONSULT', 'DONE']).order_by('-date', 'token_number')[:20]:
            date_range_queue.append({
                "token": ticket.token_number,
                "date": str(ticket.date),
                "patient": {
                    "id": ticket.patient.id,
                    "name": ticket.patient.user.full_name,
                    "mrn": ticket.patient.patient_id,
                    "age": self.calculate_age(ticket.patient.date_of_birth),
                    "gender": ticket.patient.gender,
                    "contact": ticket.patient.phone or "",
                },
                "doctor": {
                    "id": ticket.assigned_doctor.id if ticket.assigned_doctor else None,
                    "name": ticket.assigned_doctor.full_name if ticket.assigned_doctor else "Unassigned",
                } if ticket.assigned_doctor else None,
                "status": ticket.get_status_display(),
                "arrival_time": ticket.created_at.strftime("%I:%M %p") if ticket.created_at else "",
                "wait_time": self.calculate_wait_time(ticket.created_at) if ticket.created_at else 0,
            })
        
        # ========== 7. Date Range Appointments ==========
        range_appointments = []
        for apt in filtered_appointments.select_related('patient__user', 'doctor').order_by('appointment_date', 'appointment_time')[:15]:
            range_appointments.append({
                "id": apt.id,
                "date": apt.appointment_date.strftime("%d %b %Y"),
                "time": apt.appointment_time or "10:00 AM",
                "patient_name": apt.patient.user.full_name,
                "patient_mrn": apt.patient.patient_id,
                "doctor_id": apt.doctor.id if apt.doctor else None,
                "doctor_name": apt.doctor.full_name if apt.doctor else "Unassigned",
                "type": apt.visit_reason,
                "status": apt.status,
                "contact": apt.patient.phone or "",
                "email": apt.patient.user.email or ""
            })
        
        # ========== 8. Doctor Status ==========
        doctors = User.objects.filter(role__in=['END', 'GYN', 'ANE'], is_active=True)
        doctor_status = []
        for doctor in doctors:
            doctor_tickets = filtered_tickets.filter(assigned_doctor=doctor)
            doctor_status.append({
                "id": doctor.id,
                "name": doctor.full_name,
                "specialization": "IVF Specialist",
                "room": getattr(doctor, 'room_number', '101'),
                "status": self.get_doctor_status_range(doctor, filtered_tickets),
                "status_color": "green",
                "patients_seen_in_range": doctor_tickets.filter(status='DONE').count(),
                "total_capacity": 15 * max(1, (end_date - start_date).days + 1),
                "current_patient": None,
                "next_patient": None,
                "queue_size": 0,
                "on_break": False,
                "break_until": None
            })
        
        # ========== 9. Room Status ==========
        if date_range == 'daily':
            room_status = []
            for idx, doctor in enumerate(doctors[:5]):
                current_patient = self.get_current_patient(doctor, filtered_tickets)
                room_status.append({
                    "room_no": f"10{idx+1}",
                    "doctor": doctor.full_name,
                    "status": "occupied" if current_patient else "available",
                    "current_patient": current_patient
                })
        else:
            room_status = []
        
        # ========== 10. Registered in Range ==========
        registered_in_range = []
        for patient in PatientProfile.objects.filter(
            registered_on__gte=start_date,
            registered_on__lte=end_date
        ).select_related('user', 'assigned_doctor')[:10]:
            registered_in_range.append({
                "date": patient.registered_on.strftime("%d %b %Y") if patient.registered_on else "",
                "time": patient.registered_on.strftime("%I:%M %p") if patient.registered_on else "",
                "patient_name": patient.user.full_name,
                "mrn": patient.patient_id,
                "contact": patient.phone or "",
                "assigned_doctor": patient.assigned_doctor.full_name if patient.assigned_doctor else "Not Assigned",
                "insurance_verified": False
            })
        
        # ========== 11. Upcoming Appointments ==========
        next_week = today + timedelta(days=7)
        upcoming_tickets = OPTicket.objects.filter(
            date__gte=today,
            date__lte=next_week,
            status__in=['WAITING', 'PENDING']
        ).select_related('patient__user', 'assigned_doctor')[:20]
        
        upcoming_appointments = []
        for ticket in upcoming_tickets:
            upcoming_appointments.append({
                "date": ticket.date.isoformat(),
                "day": weekdays[ticket.date.weekday()],
                "patient_name": ticket.patient.user.full_name,
                "patient_mrn": ticket.patient.patient_id,
                "doctor_name": ticket.assigned_doctor.full_name if ticket.assigned_doctor else "Unassigned",
                "time": "10:00 AM",
                "status": ticket.status,
                "contact": ticket.patient.phone or "",
                "reminder_sent": False
            })
        
        # ========== 12. Quick Stats ==========
        quick_stats = {
            "range_label": range_label,
            "total_days": (end_date - start_date).days + 1,
            "total_tickets": filtered_tickets.count(),
            "total_appointments": filtered_appointments.count(),
            "total_patients_in_range": PatientProfile.objects.filter(
                registered_on__gte=start_date,
                registered_on__lte=end_date
            ).count(),
            "avg_daily_tickets": round(filtered_tickets.count() / max(1, (end_date - start_date).days + 1), 1),
            "avg_wait_time": self.calculate_average_wait_time(filtered_tickets),
            "peak_hour": self.get_peak_hour(filtered_tickets),
            "peak_hour_count": self.get_peak_hour_count(filtered_tickets),
            "cancellation_rate": round((filtered_tickets.filter(status='CANCELLED').count() / max(1, filtered_tickets.count())) * 100, 1),
            "no_show_rate": round((filtered_appointments.filter(status='NO_SHOW').count() / max(1, filtered_appointments.count())) * 100, 1),
            "completion_rate": round((filtered_tickets.filter(status='DONE').count() / max(1, filtered_tickets.count())) * 100, 1)
        }
        
        # ========== 13. Charts Data ==========
        days_list = []
        tickets_list = []
        appointments_list = []
        
        delta = (end_date - start_date).days
        if delta <= 7:
            current = start_date
            while current <= end_date:
                days_list.append(current.strftime("%a, %d %b"))
                tickets_list.append(OPTicket.objects.filter(date=current).count())
                appointments_list.append(Appointment.objects.filter(appointment_date=current).count())
                current += timedelta(days=1)
        else:
            current = start_date
            while current <= end_date:
                week_end = min(current + timedelta(days=6), end_date)
                week_label = f"{current.strftime('%d %b')} - {week_end.strftime('%d %b')}"
                days_list.append(week_label)
                tickets_list.append(OPTicket.objects.filter(date__gte=current, date__lte=week_end).count())
                appointments_list.append(Appointment.objects.filter(appointment_date__gte=current, appointment_date__lte=week_end).count())
                current = week_end + timedelta(days=1)
        
        hourly_labels = ["9 AM", "10 AM", "11 AM", "12 PM", "1 PM", "2 PM", "3 PM", "4 PM", "5 PM"]
        hourly_values = []
        for hour in range(9, 18):
            count = filtered_tickets.filter(created_at__hour=hour).count()
            hourly_values.append(count)
        
        charts_data = {
            "patient_flow": {
                "labels": days_list,
                "values": tickets_list,
                "appointment_values": appointments_list
            },
            "hourly_distribution": {
                "labels": hourly_labels,
                "values": hourly_values
            },
            "weekly_trend": {
                "labels": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat"],
                "values": [0, 0, 0, 0, 0, 0]
            },
            "wait_times": {
                "labels": hourly_labels[:-1],
                "values": [0, 0, 0, 0, 0, 0, 0, 0]
            }
        }
        
        # ========== 14. Notifications ==========
        notifications = [
            {
                "id": 1,
                "type": "warning",
                "title": "Insurance Verification Pending",
                "message": "3 patients require insurance verification",
                "time": current_time.isoformat(),
                "read": False,
                "action_required": True,
                "action_url": "/insurance/pending"
            }
        ]
        
        # ========== 15. Billing Summary ==========
        billing_summary = {
            "today_collections": 0.00,
            "pending_payments": 5000.00,
            "insurance_claims_pending": 3,
            "insurance_claims_approved": 2,
            "insurance_claims_rejected": 0,
            "last_transaction": None
        }
        
        # ========== Final Response ==========
        return Response({
            'date_range_info': {
                'range': date_range,
                'label': range_label,
                'start_date': str(start_date),
                'end_date': str(end_date)
            },
            'receptionist_info': receptionist_info,
            'clinic_info': clinic_info,
            'todays_stats': todays_stats,
            'queue_stats': queue_stats,
            'patient_metrics': patient_metrics,
            'today_queue': date_range_queue,
            'today_appointments': range_appointments,
            'doctor_status': doctor_status,
            'room_status': room_status,
            'registered_today': registered_in_range,
            'upcoming_appointments': upcoming_appointments,
            'quick_stats': quick_stats,
            'charts_data': charts_data,
            'notifications': notifications,
            'billing_summary': billing_summary
        })
    
    # ========== Helper Methods ==========
    
    def calculate_age(self, date_of_birth):
        if not date_of_birth:
            return None
        today = timezone.now().date()
        return today.year - date_of_birth.year - ((today.month, today.day) < (date_of_birth.month, date_of_birth.day))
    
    def calculate_wait_time(self, created_at):
        if not created_at:
            return 0
        delta = timezone.now() - created_at
        return int(delta.total_seconds() / 60)
    
    def calculate_average_wait_time(self, tickets):
        wait_times = []
        for ticket in tickets:
            if ticket.created_at:
                delta = timezone.now() - ticket.created_at
                wait_times.append(int(delta.total_seconds() / 60))
        return round(sum(wait_times) / len(wait_times), 1) if wait_times else 0
    
    def get_peak_hour(self, tickets):
        hour_counts = {}
        for ticket in tickets:
            if ticket.created_at:
                hour = ticket.created_at.hour
                hour_counts[hour] = hour_counts.get(hour, 0) + 1
        if hour_counts:
            peak_hour = max(hour_counts, key=hour_counts.get)
            return f"{peak_hour % 12 or 12}:00 {'AM' if peak_hour < 12 else 'PM'}"
        return None
    
    def get_peak_hour_count(self, tickets):
        hour_counts = {}
        for ticket in tickets:
            if ticket.created_at:
                hour = ticket.created_at.hour
                hour_counts[hour] = hour_counts.get(hour, 0) + 1
        return max(hour_counts.values()) if hour_counts else 0
    
    def get_current_serving_token(self, today_tickets):
        current = today_tickets.filter(status='IN_CONSULT').first()
        if current:
            return current.token_number
        waiting = today_tickets.filter(status='WAITING').first()
        if waiting:
            return waiting.token_number
        return 0
    
    def get_doctor_status(self, doctor, today_tickets):
        if today_tickets.filter(assigned_doctor=doctor, status='IN_CONSULT').exists():
            return "in_consultation"
        if today_tickets.filter(assigned_doctor=doctor, status='WAITING').exists():
            return "waiting"
        return "available"
    
    def get_doctor_status_range(self, doctor, tickets):
        if tickets.filter(assigned_doctor=doctor, status='IN_CONSULT').exists():
            return "in_consultation"
        if tickets.filter(assigned_doctor=doctor, status='WAITING').exists():
            return "waiting"
        return "available"
    
    def get_current_patient(self, doctor, today_tickets):
        current = today_tickets.filter(assigned_doctor=doctor, status='IN_CONSULT').first()
        if current:
            return current.patient.user.full_name
        return None
    
    def get_returning_patients_count(self):
        from django.db.models import Count
        return PatientProfile.objects.annotate(
            ticket_count=Count('op_tickets')
        ).filter(ticket_count__gt=1).count()
    
    def get_returning_patients_count_range(self, start_date, end_date):
        from django.db.models import Count
        return PatientProfile.objects.filter(
            op_tickets__date__gte=start_date,
            op_tickets__date__lte=end_date
        ).annotate(
            ticket_count=Count('op_tickets')
        ).filter(ticket_count__gt=1).distinct().count()

    def get(self, request):
        today = timezone.now().date()
        current_time = timezone.now()
        
        weekdays = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        today_tickets = OPTicket.objects.filter(date=today)
        user = request.user
        
        # ========== 1. Receptionist Info ==========
        receptionist_info = {
            "id": user.id,
            "name": user.full_name,
            "role": "Receptionist",
            "profile_image": None,
            "employee_id": f"REC{user.id:04d}",
            "shift": "Morning (9:00 AM - 5:00 PM)",
            "join_date": user.date_joined.date().isoformat() if user.date_joined else "2024-01-01"
        }
        
        # ========== 2. Clinic Info ==========
        clinic_info = {
            "name": "IVF Speciality Clinic",
            "location": "Kochi, Kerala",
            "contact": "+91 484 1234567",
            "working_hours": "9:00 AM - 6:00 PM",
            "current_time": current_time.isoformat(),
            "current_date": f"{weekdays[current_time.weekday()]}, {current_time.strftime('%d %B %Y')}"
        }
        
        # ========== 3. Today's Stats ==========
        todays_stats = {
            "patients_registered": PatientProfile.objects.filter(registered_on=today).count(),
            "tickets_generated": today_tickets.count(),
            "walkin_patients": Appointment.objects.filter(appointment_date=today, appointment_type='WALK_IN').count(),
            "appointments_scheduled": Appointment.objects.filter(appointment_date=today).count(),
            "appointments_completed": today_tickets.filter(status='DONE').count(),
            "appointments_missed": 0,
            "appointments_cancelled": today_tickets.filter(status='CANCELLED').count(),
            "revenue_collected": 0.00,
            "pending_payments": 0.00,
            "insurance_claims": 0
        }
        
        # ========== 4. Queue Stats ==========
        queue_stats = {
            "total_waiting": today_tickets.filter(status='WAITING').count(),
            "in_consultation": today_tickets.filter(status='IN_CONSULT').count(),
            "completed": today_tickets.filter(status='DONE').count(),
            "cancelled": today_tickets.filter(status='CANCELLED').count(),
            "no_shows": 0,
            "next_token": OPTicket.next_token_for_today(),
            "current_serving": self.get_current_serving_token(today_tickets),
            "average_wait_time": 0,
            "peak_hour": None,
            "queue_status": "active" if today_tickets.exists() else "inactive"
        }
        
        # ========== 5. Patient Metrics ==========
        current_month = today.month
        current_year = today.year
        patient_metrics = {
            "total_patients": PatientProfile.objects.count(),
            "new_patients_this_month": PatientProfile.objects.filter(
                registered_on__year=current_year,
                registered_on__month=current_month
            ).count(),
            "returning_patients": self.get_returning_patients_count(),
            "active_treatments": PatientProfile.objects.filter(status='ACTIVE').count(),
            "completed_treatments": PatientProfile.objects.filter(status='COMPLETED').count(),
            "patient_satisfaction_rate": 4.8,
            "ratings_count": 258
        }
        
        # ========== 6. Today's Queue ==========
        today_queue = []
        for ticket in today_tickets.filter(status__in=['WAITING', 'IN_CONSULT']).order_by('token_number')[:20]:
            today_queue.append({
                "token": ticket.token_number,
                "patient": {
                    "id": ticket.patient.id,
                    "name": ticket.patient.user.full_name,
                    "mrn": ticket.patient.patient_id,
                    "age": self.calculate_age(ticket.patient.date_of_birth),
                    "gender": ticket.patient.gender,
                    "contact": ticket.patient.phone or "",
                },
                "doctor": {
                    "id": ticket.assigned_doctor.id if ticket.assigned_doctor else None,
                    "name": ticket.assigned_doctor.full_name if ticket.assigned_doctor else "Unassigned",
                    "specialization": "IVF Specialist",
                    "room": "101",
                } if ticket.assigned_doctor else None,
                "status": ticket.get_status_display(),
                "arrival_time": ticket.created_at.strftime("%I:%M %p") if ticket.created_at else "",
                "wait_time": self.calculate_wait_time(ticket.created_at),
                "consultation_type": "General",
                "priority": "normal"
            })
        
        # ========== 7. Today's Appointments ==========
        today_appointments = []
        for ticket in today_tickets.order_by('created_at')[:15]:
            today_appointments.append({
                "id": ticket.id,
                "time": ticket.created_at.strftime("%I:%M %p") if ticket.created_at else "",
                "patient_name": ticket.patient.user.full_name,
                "patient_mrn": ticket.patient.patient_id,
                "doctor_id": ticket.assigned_doctor.id if ticket.assigned_doctor else None,
                "doctor_name": ticket.assigned_doctor.full_name if ticket.assigned_doctor else "Unassigned",
                "room": "101",
                "type": "Consultation",
                "status": ticket.status,
                "contact": ticket.patient.phone or "",
                "email": ticket.patient.user.email or ""
            })
        
        # ========== 8. Doctor Status ==========
        doctors = User.objects.filter(role__in=['END', 'GYN', 'ANE'], is_active=True)
        doctor_status = []
        for doctor in doctors:
            doctor_tickets = today_tickets.filter(assigned_doctor=doctor)
            doctor_status.append({
                "id": doctor.id,
                "name": doctor.full_name,
                "specialization": "IVF Specialist",
                "room": getattr(doctor, 'room_number', '101'),
                "status": self.get_doctor_status(doctor, today_tickets),
                "status_color": self.get_doctor_status_color(doctor, today_tickets),
                "patients_seen_today": doctor_tickets.filter(status='DONE').count(),
                "total_capacity": 15,
                "current_patient": self.get_current_patient(doctor, today_tickets),
                "next_patient": self.get_next_patient(doctor, today_tickets),
                "queue_size": doctor_tickets.filter(status='WAITING').count(),
                "on_break": False,
                "break_until": None
            })
        
        # ========== 9. Room Status ==========
        room_status = []
        for idx, doctor in enumerate(doctors[:5]):
            current_patient = self.get_current_patient(doctor, today_tickets)
            room_status.append({
                "room_no": f"10{idx+1}",
                "doctor": doctor.full_name,
                "status": "occupied" if current_patient else "available",
                "current_patient": current_patient
            })
        
        # ========== 10. Registered Today ==========
        registered_today = []
        for patient in PatientProfile.objects.filter(registered_on=today).select_related('user', 'assigned_doctor')[:10]:
            registered_today.append({
                "time": patient.registered_on.strftime("%I:%M %p") if patient.registered_on else "",
                "patient_name": patient.user.full_name,
                "mrn": patient.patient_id,
                "contact": patient.phone or "",
                "assigned_doctor": patient.assigned_doctor.full_name if patient.assigned_doctor else "Not Assigned",
                "insurance_verified": False
            })
        
        # ========== 11. Upcoming Appointments ==========
        next_week = today + timedelta(days=7)
        upcoming_tickets = OPTicket.objects.filter(
            date__gt=today,
            date__lte=next_week,
            status__in=['WAITING', 'PENDING']
        ).select_related('patient__user', 'assigned_doctor')[:20]
        
        upcoming_appointments = []
        for ticket in upcoming_tickets:
            upcoming_appointments.append({
                "date": ticket.date.isoformat(),
                "day": weekdays[ticket.date.weekday()],
                "patient_name": ticket.patient.user.full_name,
                "patient_mrn": ticket.patient.patient_id,
                "doctor_name": ticket.assigned_doctor.full_name if ticket.assigned_doctor else "Unassigned",
                "time": "10:00 AM",
                "status": ticket.status,
                "contact": ticket.patient.phone or "",
                "reminder_sent": False
            })
        
        # ========== 12. Quick Stats ==========
        start_of_week = today - timedelta(days=today.weekday())
        weekly_patients = PatientProfile.objects.filter(registered_on__gte=start_of_week).count()
        monthly_patients = PatientProfile.objects.filter(
            registered_on__year=current_year,
            registered_on__month=current_month
        ).count()
        
        quick_stats = {
            "this_week_patients": weekly_patients,
            "this_month_patients": monthly_patients,
            "avg_daily_patients": int(monthly_patients / 30) if monthly_patients > 0 else 0,
            "avg_wait_time_weekly": 12.5,
            "peak_hour": "11:00 AM",
            "peak_hour_count": 24,
            "cancellation_rate": 5.2,
            "no_show_rate": 3.8
        }
        
        # ========== 13. Charts Data ==========
        hourly_data = []
        for hour in range(9, 18):
            count = OPTicket.objects.filter(date=today, created_at__hour=hour).count()
            hourly_data.append(count)
        
        charts_data = {
            "patient_flow": {
                "labels": ["9 AM", "10 AM", "11 AM", "12 PM", "1 PM", "2 PM", "3 PM", "4 PM", "5 PM"],
                "values": hourly_data
            },
            "weekly_trend": {
                "labels": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat"],
                "values": [0, 0, 0, 0, 0, 0]
            },
            "wait_times": {
                "labels": ["9 AM", "10 AM", "11 AM", "12 PM", "1 PM", "2 PM", "3 PM", "4 PM"],
                "values": [0, 0, 0, 0, 0, 0, 0, 0]
            }
        }
        
        # ========== 14. Notifications ==========
        notifications = [
            {
                "id": 1,
                "type": "warning",
                "title": "Insurance Verification Pending",
                "message": "3 patients require insurance verification",
                "time": current_time.isoformat(),
                "read": False,
                "action_required": True,
                "action_url": "/insurance/pending"
            }
        ]
        
        # ========== 15. Billing Summary ==========
        billing_summary = {
            "today_collections": 0.00,
            "pending_payments": 5000.00,
            "insurance_claims_pending": 3,
            "insurance_claims_approved": 2,
            "insurance_claims_rejected": 0,
            "last_transaction": None
        }
        
        # ========== Final Response (without recent_patients) ==========
        return Response({
            'receptionist_info': receptionist_info,
            'clinic_info': clinic_info,
            'todays_stats': todays_stats,
            'queue_stats': queue_stats,
            'patient_metrics': patient_metrics,
            'today_queue': today_queue,
            'today_appointments': today_appointments,
            'doctor_status': doctor_status,
            'room_status': room_status,
            'registered_today': registered_today,
            'upcoming_appointments': upcoming_appointments,
            'quick_stats': quick_stats,
            'charts_data': charts_data,
            'notifications': notifications,
            'billing_summary': billing_summary
        })
    
    # ========== Helper Methods ==========
    
    def calculate_age(self, date_of_birth):
        if not date_of_birth:
            return None
        today = timezone.now().date()
        return today.year - date_of_birth.year - ((today.month, today.day) < (date_of_birth.month, date_of_birth.day))
    
    def calculate_wait_time(self, created_at):
        if not created_at:
            return 0
        delta = timezone.now() - created_at
        return int(delta.total_seconds() / 60)
    
    def get_current_serving_token(self, today_tickets):
        current = today_tickets.filter(status='IN_CONSULT').first()
        if current:
            return current.token_number
        waiting = today_tickets.filter(status='WAITING').first()
        if waiting:
            return waiting.token_number
        return 0
    
    def get_doctor_status(self, doctor, today_tickets):
        if today_tickets.filter(assigned_doctor=doctor, status='IN_CONSULT').exists():
            return "in_consultation"
        if today_tickets.filter(assigned_doctor=doctor, status='WAITING').exists():
            return "waiting"
        return "available"
    
    def get_doctor_status_color(self, doctor, today_tickets):
        status = self.get_doctor_status(doctor, today_tickets)
        colors = {
            "available": "green",
            "in_consultation": "yellow",
            "waiting": "orange"
        }
        return colors.get(status, "gray")
    
    def get_current_patient(self, doctor, today_tickets):
        current = today_tickets.filter(assigned_doctor=doctor, status='IN_CONSULT').first()
        if current:
            return current.patient.user.full_name
        return None
    
    def get_next_patient(self, doctor, today_tickets):
        next_ticket = today_tickets.filter(assigned_doctor=doctor, status='WAITING').order_by('token_number').first()
        if next_ticket:
            return next_ticket.patient.user.full_name
        return None
    
    def get_returning_patients_count(self):
        return PatientProfile.objects.annotate(
            ticket_count=Count('op_tickets')
        ).filter(ticket_count__gt=1).count()