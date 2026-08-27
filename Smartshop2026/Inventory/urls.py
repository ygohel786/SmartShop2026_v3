from django.urls import path
from . import views

urlpatterns = [
    path('sales/', views.sales, name='sales'),
    path('hx_add_bill_item/', views.hx_add_bill_item, name='hx_add_bill_item'),
    path('generate_bill/', views.generate_bill, name='generate_bill'),
    path('inventory/', views.inventory_view, name='inventory'),
]