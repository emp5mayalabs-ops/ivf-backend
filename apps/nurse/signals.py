# # apps/nurse/signals.py
# from django.db.models.signals import post_save
# from django.dispatch import receiver
# from django.contrib.auth import get_user_model
# from accounts.models import NurseProfile

# User = get_user_model()


# @receiver(post_save, sender=User)
# def create_nurse_profile(sender, instance, created, **kwargs):
#     """Auto create nurse profile when user with role NUR is created"""
#     if created and instance.role == 'NUR':
#         NurseProfile.objects.get_or_create(user=instance)