import os
import django

# 1. Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ivf.settings')
django.setup()

from django.contrib.auth import get_user_model

User = get_user_model()

email = 'shravan@gmail.com'
password = 'shravan123'

if not User.objects.filter(email=email).exists():
     User.objects.create_superuser(email=email,password=password)
     print(f"Superuser {email} created successfully!")
else:
  print(f"User with email {email} already exists.")