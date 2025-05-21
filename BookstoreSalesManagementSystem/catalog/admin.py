from django.contrib import admin
from .models import Book, Customer, Order, OrderItem

# Register your models here.
admin.site.register(Customer)


@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    list_display = ('title', 'price', 'stock')


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('order_id', 'order_date', 'status')
    list_filter = ('status',)


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ('order_item_id', 'book', 'count', 'order_id')
    list_filter = ('order_id',)
