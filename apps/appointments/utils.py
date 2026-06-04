import qrcode
from io import BytesIO
import base64
from django.conf import settings

def generate_ticket_qr_code(ticket):
    """
    Generate QR code for a ticket as base64 string.
    Returns: base64 string that can be used as img src
    """
    # Create URL or data to encode in QR
    # You can customize this based on your needs
    frontend_url = getattr(settings, 'FRONTEND_URL', 'http://localhost:3000')
    
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
    
    # Convert to JSON string
    import json
    qr_string = json.dumps(qr_data)
    
    # Generate QR code
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(qr_string)
    qr.make(fit=True)
    
    # Create image
    img = qr.make_image(fill_color="black", back_color="white")
    
    # Convert to base64
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    img_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
    
    return f"data:image/png;base64,{img_base64}"