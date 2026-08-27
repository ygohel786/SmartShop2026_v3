from django.db import models
from django.contrib.auth.models import AbstractUser

class ShopUser(AbstractUser):
    shop_name = models.CharField(max_length=150)
    contact_no = models.CharField(max_length=15)
    street = models.CharField(max_length=150, blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    pin_code = models.CharField(max_length=10, blank=True)

    def __str__(self):
        return f"{self.username} - {self.shop_name}"