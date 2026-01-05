from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Hotel, CashRegister

@receiver(post_save, sender=Hotel)
def ensure_cash_register(sender, instance, created, **kwargs):
    if created:
        CashRegister.objects.get_or_create(hotel=instance)
