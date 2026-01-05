from django.db import models

# Create your models here.
from django.conf import settings
from django.db import models

# ВАЖНО: импортируй Hotel из dds (или из твоего приложения филиалов)
from dds.models import Hotel


class Profile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile")
    hotel = models.ForeignKey(Hotel, on_delete=models.PROTECT, null=True, blank=True)

    # это твой флаг “главный бухгалтер/финансист” (видит все отели)
    is_finance_admin = models.BooleanField(default=False)

    def __str__(self):
        return f"Profile: {self.user}"
