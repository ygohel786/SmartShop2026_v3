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
    
    business_type = models.CharField(max_length=50, choices=BUSINESS_CHOICES, default='General')

    street = models.CharField(max_length=150, blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    pin_code = models.CharField(max_length=10, blank=True)

    # ==========================================
    # 👨‍💼 સ્ટાફ મેનેજમેન્ટ માટે નવા ઉમેરેલા ફિલ્ડ્સ
    # ==========================================
    is_shop_staff = models.BooleanField(default=False, help_text="ટીક કરો જો આ એકાઉન્ટ દુકાનના સ્ટાફ/વર્કરનું હોય")
    
    parent_shop = models.ForeignKey(
        'self', 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True, 
        related_name='staff_members',
        help_text="જો આ સ્ટાફ હોય, તો તેના મુખ્ય માલિક (Owner) કયા છે?"
    )

    def __str__(self):
        if self.is_shop_staff and self.parent_shop:
            return f"Staff: {self.username} (Owner: {self.parent_shop.shop_name})"
        return f"Owner: {self.username} - {self.shop_name}"

    @property
    def get_shop(self):
        """ 
        જાદુઈ ફંક્શન: 
        જો સ્ટાફ લોગીન હશે, તો આ ફંક્શન માલિક (Owner) નું એકાઉન્ટ આપશે.
        જો માલિક લોગીન હશે, તો તે પોતાનું જ એકાઉન્ટ આપશે.
        (આનાથી આપણે આખા પ્રોજેક્ટમાં દુકાનદારને શોધવો સરળ બની જશે)
        """
        return self.parent_shop if self.is_shop_staff else self