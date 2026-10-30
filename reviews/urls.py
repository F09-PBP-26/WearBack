from django.urls import path

from reviews import views

app_name = 'reviews'
urlpatterns = [
    path('', views.review_list, name='list'),
    path('order/<int:transaction_id>/create/', views.review_create, name='create'),
    path('<int:pk>/edit/', views.review_edit, name='edit'),
    path('<int:pk>/delete/', views.review_delete, name='delete'),
]
