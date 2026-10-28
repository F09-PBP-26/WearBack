from django.urls import path

from listings import views

app_name = 'listings'

urlpatterns = [
    path('', views.index, name='index'),
    path('create/', views.create, name='create'),
    path('mine/', views.mine, name='mine'),
    path('<int:pk>/', views.detail, name='detail'),
    path('<int:pk>/edit/', views.update, name='update'),
    path('<int:pk>/delete/', views.delete, name='delete'),
]
