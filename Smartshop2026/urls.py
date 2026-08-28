from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # Account અને Inventory ના પાથ ડાયરેક્ટ ચાલશે
    path('', include('Account.urls')),
    path('', include('Inventory.urls')),
    
    # Analysis ને 'analysis/' પાથ આપ્યો છે, જેથી કન્ફ્યુઝન ના થાય
    path('analysis/', include('Analysis.urls')),
]