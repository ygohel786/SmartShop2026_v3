from django.urls import path
from . import views

urlpatterns = [
    path('home/', views.home, name='home'), 
    
    # ઈન્વેન્ટરી મેનેજમેન્ટ
    path('inventory/', views.inventory_view, name='inventory'),
    path('add/', views.add_product, name='add_product'),
    path('edit/<int:product_id>/', views.edit_product, name='edit_product'),
    path('delete/<int:product_id>/', views.delete_product, name='delete_product'),
    path('print-barcode/<int:product_id>/', views.print_barcodes, name='print_barcodes'),
    
    # સેલ્સ અને બિલિંગ
    path('sales/', views.sales, name='sales'),
    path('hx_add_bill_item/', views.hx_add_bill_item, name='hx_add_bill_item'),
    path('generate_bill/', views.generate_bill, name='generate_bill'),
    path('sales-history/', views.sales_history, name='sales_history'),
    path('invoice/<int:invoice_id>/', views.print_invoice, name='print_invoice'),
    
    # Khata Book / Ledger Module
    path('khata/', views.khata_dashboard, name='khata_dashboard'),
    path('khata/add-customer/', views.add_khata_customer, name='add_khata_customer'),
    path('khata/<int:customer_id>/', views.khata_detail, name='khata_detail'),
    path('khata/<int:customer_id>/add-transaction/', views.add_khata_transaction, name='add_khata_transaction'),
]