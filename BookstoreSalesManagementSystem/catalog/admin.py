from django.contrib import admin
from .models import Book, Customer, Order, OrderItem

# Superuser
# Username: admin
# Password: admin

# Register your models here.
admin.site.register(Book)
admin.site.register(Customer)
admin.site.register(Order)
admin.site.register(OrderItem)
