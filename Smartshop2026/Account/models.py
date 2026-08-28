from django.db import models
from django.contrib.auth.models import AbstractUser

class ShopUser(AbstractUser):
    # દુકાનના પ્રકાર માટેના ઓપ્શન્સ
    BUSINESS_CHOICES = [
        ('General', 'General Store / Hardware'),
        ('Food', 'Food / Pharmacy / FMCG'),
        ('Electronics', 'Electronics / Mobile / IT'),
        ('Apparel', 'Apparel / Footwear'),
    ]

    shop_name = models.CharField(max_length=150)
    contact_no = models.CharField(max_length=15)
    
    # નવું ઉમેરેલું ફિલ્ડ
    business_type = models.CharField(max_length=50, choices=BUSINESS_CHOICES, default='General')

    street = models.CharField(max_length=150, blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    pin_code = models.CharField(max_length=10, blank=True)

    def __str__(self):
        return f"{self.username} - {self.shop_name} ({self.business_type})"