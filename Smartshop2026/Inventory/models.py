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
    name = models.CharField(max_length=200)
    purchase_price = models.DecimalField(max_digits=10, decimal_places=2)
    margin_percentage = models.DecimalField(max_digits=5, decimal_places=2)
    
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

class InvoiceItem(models.Model):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField()
    selling_price = models.DecimalField(max_digits=10, decimal_places=2)
    sub_total = models.DecimalField(max_digits=10, decimal_places=2)

    def save(self, *args, **kwargs):
        self.sub_total = self.quantity * self.selling_price
        super().save(*args, **kwargs)
        # વેચાણ થાય ત્યારે આપમેળે સ્ટોક માઈનસ થશે
        StockMovement.objects.create(
            product=self.product,
            movement_type='OUT',
            quantity=self.quantity,
            notes=f"Sold on Invoice {self.invoice.id}"
        )