from django.contrib import admin
from .models import ShopUser

# આ લાઈનથી તમારું મોડલ એડમિનમાં દેખાવા લાગશે
admin.site.register(ShopUser)