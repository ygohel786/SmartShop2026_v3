from django import forms
from .models import Product, Category, Invoice

class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ['category', 'name', 'purchase_price', 'margin_percentage']
        widgets = {
            'category': forms.Select(attrs={'class': 'form-control'}),
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter Product Name'}),
            'purchase_price': forms.NumberInput(attrs={'class': 'form-control'}),
            'margin_percentage': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'e.g. 15 for 15%'}),
        }

class InvoiceForm(forms.ModelForm):
    class Meta:
        model = Invoice
        fields = ['customer_name', 'contact_number', 'gst_number']
        widgets = {
            'customer_name': forms.TextInput(attrs={'class': 'form-control'}),
            'contact_number': forms.TextInput(attrs={'class': 'form-control'}),
            'gst_number': forms.TextInput(attrs={'class': 'form-control'}),
        }