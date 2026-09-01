from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # Account અને Inventory ના પાથ ડાયરેક્ટ ચાલશે
    path('', include('Account.urls')),
    path('', include('Inventory.urls')),
    
    # Analysis ને 'analysis/' પાથ આપ્યો છે, જેથી કન્ફ્યુઝન ના થાય
    path('analysis/', include('Analysis.urls')),
    
]
    # Media ફાઈલો (જેમ કે અપલોડ કરેલા બિલના ફોટા) બતાવવા માટે
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)