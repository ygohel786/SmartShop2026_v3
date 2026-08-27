from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    # આપણી ત્રણેય એપ્સના URLs અહી જોડી દીધા છે:
    path('', include('Account.urls')),
    path('', include('Inventory.urls')),
    path('', include('Analysis.urls')),
]