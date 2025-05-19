from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('books/', views.BookListView.as_view(), name='books'),
    path('books/<str:pk>/', views.BookDetailView.as_view(), name='book_detail'),
    path('orders/', views.OrderListView.as_view(), name='orders'),
    path('order/<int:order_id>/', views.OrderDetailView.as_view(), name='order_detail'),
]
