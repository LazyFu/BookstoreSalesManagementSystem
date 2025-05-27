from django.urls import path, reverse_lazy
from . import views
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('', views.index, name='index'),
    path('books/', views.BookListView.as_view(), name='books'),
    path('books/<str:pk>/', views.BookDetailView.as_view(), name='book_detail'),
    path('orders/', views.OrderListView.as_view(), name='orders'),
    path('order/<int:pk>/', views.OrderDetailView.as_view(), name='order_detail'),
    path('cart/add/<str:isbn>/', views.add_to_cart, name='add_to_cart'),
    path('cart/update/', views.update_cart, name='update_cart'),
    path('cart/clear/', views.clear_cart, name='clear_cart'),
    path('cart/', views.view_cart, name='view_cart'),
    path('checkout/', views.checkout, name='checkout'),

    path('auth/login/', auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'),
    path('auth/logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('auth/signup/', views.signup_view, name='signup'),
    #    path('profile/', views.profile_view, name='profile'),
    path('profile/edit/', views.edit_profile_view, name='profile_edit'),
    path('simplified_forgot_password/',
         views.simplified_forgot_password_request_view,
         name='simplified_forgot_password_request'),

    path('simplified_set_new_password/',
         views.simplified_set_new_password_view,
         name='simplified_set_new_password'),
]
