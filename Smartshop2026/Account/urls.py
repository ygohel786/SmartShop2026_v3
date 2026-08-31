from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'), 
    path('signup/', views.signup, name='signup'), 
    path('logout/', views.logout_view, name='logout'),
    
    path('profile/', views.profile_view, name='profile'),
    path('change-password/', views.change_password, name='change_password'),
]