from django.urls import path
from . import views

urlpatterns = [
    # મેઈન ડેશબોર્ડ પેજ માટે (મેઈન ફાઈલમાંથી 'analysis/' લાગીને આવશે)
    path('', views.analysis, name='analysis'),
    
    # તમારી JSON API માટે
    path('overall/', views.overall, name='overall'),
]