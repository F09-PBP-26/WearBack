from django.contrib import admin
from django.urls import path

from main import views

app_name = 'main'

urlpatterns = [
    path('', views.show_main, name='show_main'),
    path('sign-in/', views.sign_in, name='sign_in'),
    path('register/', views.register, name='register'),
]
