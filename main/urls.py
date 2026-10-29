from django.urls import path

from main import views
from main.review_views import review_preview

app_name = 'main'

urlpatterns = [
    path('', views.show_main, name='show_main'),
    path('auction/', views.auction, name='auction'),
    path('reviews/preview/', review_preview, name='review_preview'),
    path('login/', views.login, name='login'),
    path('register/', views.register, name='register'),
    path('logout/', views.logout, name='logout'),
    path('profile/', views.profile, name='profile'),

    # Transaction
    path("transactions/", views.transaction_history, name="transaction_history"),

    # Cart
    path("cart/", views.cart, name="cart"),
    path("cart/<int:item_id>/remove/", views.remove_cart_item, name="remove_cart_item"),
    path("cart/checkout/", views.checkout_cart, name="checkout_cart"),
    path("cart/add/<int:listing_id>/", views.add_to_cart, name="add_to_cart"),

    path('sso/login/', views.sso_login, name='sso_login'),
    path('sso/callback/', views.sso_callback, name='sso_callback'),
    path('sso/link/', views.sso_link, name='sso_link'),
]
