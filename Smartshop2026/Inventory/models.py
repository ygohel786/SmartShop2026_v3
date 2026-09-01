from django.db import models
from django.db.models import Sum
from Account.models import ShopUser

class Category(models.Model):
    name = models.CharField(max_length=100)
    shop = models.ForeignKey(ShopUser, on_delete=models.CASCADE, related_name='categories')

    def __str__(self):
        return self.name

class Product(models.Model):
    shop = models.ForeignKey(ShopUser, on_delete=models.CASCADE, related_name='products')
    category = models.ForeignKey(Category, on_delete=models.PROTECT)
    
    company_name = models.CharField(max_length=150, blank=True, null=True)
    product_type = models.CharField(max_length=150, blank=True, null=True)
    name = models.CharField(max_length=200)
    
    weight = models.CharField(max_length=50, blank=True, null=True)
    size = models.CharField(max_length=50, blank=True, null=True)
    storage = models.CharField(max_length=50, blank=True, null=True)
    color = models.CharField(max_length=50, blank=True, null=True)
    
    # સિસ્ટમનો પોતાનો યુનિક કોડ (SN / SKU)
    serial_number = models.CharField(max_length=100, blank=True, null=True)
        
    # 🆕 નવી કોલમ: કંપનીના ઓરિજિનલ બારકોડ (EAN/UPC) માટે 
    company_barcode = models.CharField(max_length=100, blank=True, null=True, help_text="કંપનીનો EAN/UPC બારકોડ")
    
    expiry_date = models.DateField(null=True, blank=True)
    
    purchase_price = models.DecimalField(max_digits=10, decimal_places=2)
    margin_percentage = models.DecimalField(max_digits=5, decimal_places=2)

    # 🛑 SaaS સિક્યુરિટી ફિક્સ: 
    # આનાથી સીરીયલ નંબર માત્ર એ દુકાન માટે જ યુનિક રહેશે, આખા ડેટાબેઝ માટે નહિ.
    class Meta:
        unique_together = ('shop', 'serial_number')

    @property
    def selling_price(self):
        margin_amount = (self.purchase_price * self.margin_percentage) / 100
        return self.purchase_price + margin_amount

    @property
    def current_stock(self):
        inward = self.movements.filter(movement_type='IN').aggregate(Sum('quantity'))['quantity__sum'] or 0
        outward = self.movements.filter(movement_type='OUT').aggregate(Sum('quantity'))['quantity__sum'] or 0
        return inward - outward

    def __str__(self):
        return self.name

class StockMovement(models.Model):
    MOVEMENT_CHOICES = [('IN', 'Inward'), ('OUT', 'Outward')]
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='movements')
    movement_type = models.CharField(max_length=3, choices=MOVEMENT_CHOICES)
    quantity = models.PositiveIntegerField()
    timestamp = models.DateTimeField(auto_now_add=True)
    notes = models.CharField(max_length=255, blank=True)

class Invoice(models.Model):
    shop = models.ForeignKey(ShopUser, on_delete=models.CASCADE)
    customer_name = models.CharField(max_length=150)
    contact_number = models.CharField(max_length=15)
    gst_number = models.CharField(max_length=50, blank=True)
    date = models.DateField(auto_now_add=True)
    sgst_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    cgst_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    grand_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    PAYMENT_MODES = (
        ('CASH', 'Cash (રોકડા)'),
        ('UPI', 'UPI (GPay/PhonePe)'),
        ('CARD', 'Card (ક્રેડિટ/ડેબિટ)'),
        ('UNPAID', 'Udhar (ખાતાવહીમાં બાકી)'),
    )
    payment_mode = models.CharField(max_length=20, choices=PAYMENT_MODES, default='CASH')

class InvoiceItem(models.Model):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField()
    selling_price = models.DecimalField(max_digits=10, decimal_places=2)
    sub_total = models.DecimalField(max_digits=10, decimal_places=2)

    def save(self, *args, **kwargs):
        self.sub_total = self.quantity * self.selling_price
        super().save(*args, **kwargs)
        StockMovement.objects.create(
            product=self.product,
            movement_type='OUT',
            quantity=self.quantity,
            notes=f"Sold on Invoice {self.invoice.id}"
        )
        
# ==========================================
# KHATA BOOK (LEDGER) MODULE
# ==========================================
class CustomerProfile(models.Model):
    shop = models.ForeignKey(ShopUser, on_delete=models.CASCADE)
    name = models.CharField(max_length=150)
    phone = models.CharField(max_length=15)
    address = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def total_balance(self):
        # GIVEN = માલ ઉધાર આપ્યો (બાકી રકમ વધશે)
        # RECEIVED = ગ્રાહકે પૈસા જમા કરાવ્યા (બાકી રકમ ઘટશે)
        given = self.transactions.filter(transaction_type='GIVEN').aggregate(models.Sum('amount'))['amount__sum'] or 0
        received = self.transactions.filter(transaction_type='RECEIVED').aggregate(models.Sum('amount'))['amount__sum'] or 0
        return given - received

    def __str__(self):
        return self.name

class LedgerTransaction(models.Model):
    TYPE_CHOICES = (
        ('GIVEN', 'Credit (ઉધાર આપ્યા)'),
        ('RECEIVED', 'Payment (જમા લીધા)'),
    )
    customer = models.ForeignKey(CustomerProfile, on_delete=models.CASCADE, related_name='transactions')
    transaction_type = models.CharField(max_length=10, choices=TYPE_CHOICES)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    date = models.DateTimeField(auto_now_add=True)
    description = models.CharField(max_length=255, help_text="e.g. ડિસ્પ્લે રિપેરિંગ બાકી, રોકડા જમા, વગેરે")

    def __str__(self):
        return f"{self.customer.name} - {self.transaction_type} - ₹{self.amount}"