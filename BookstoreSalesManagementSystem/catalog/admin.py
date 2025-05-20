from django.contrib import admin
from .models import Book, Customer, Order, OrderItem

# Superuser
# Username: admin
# Password: admin

# Register your models here.
# admin.site.register(Book)
admin.site.register(Customer)
# admin.site.register(Order)
# admin.site.register(OrderItem)

@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    list_display = ('title','price','stock')

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('order_id','order_date','status')
    list_filter = ('status',)

@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ('order_item_id','order_id')