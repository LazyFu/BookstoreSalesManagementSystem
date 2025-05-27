# models.py
from django.contrib.auth.models import User
from django.db import models
from django.urls import reverse


class Book(models.Model):
    isbn = models.CharField(
        verbose_name='ISBN',
        max_length=13,
        primary_key=True,
        help_text='13 Character <a href="https://www.isbn-international.org/content/what-isbn">ISBN number</a>'
    )
    title = models.CharField(verbose_name='Title', max_length=100)
    author = models.CharField(verbose_name='Author', max_length=100, null=True, blank=True)
    press = models.CharField(verbose_name='Press', max_length=100, null=True, blank=True)
    price = models.DecimalField(verbose_name='Price', max_digits=6, decimal_places=2)
    stock = models.PositiveIntegerField(verbose_name='Stock', default=0)
    summary = models.TextField(verbose_name='Summary', max_length=1000, blank=True, null=True)

    class Meta:
        verbose_name = 'Book'
        verbose_name_plural = 'Books'

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse('book_detail', args=[str(self.isbn)])


class Customer(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, primary_key=True, verbose_name='User')
    name = models.CharField(verbose_name='Name', max_length=100)
    phone = models.CharField(verbose_name='Phone', max_length=20)  # Increased max_length

    class Meta:
        verbose_name = 'Customer'
        verbose_name_plural = 'Customers'

    def __str__(self):
        return self.user.username


class Order(models.Model):
    order_id = models.AutoField(verbose_name='Order ID', primary_key=True)
    customer = models.ForeignKey(
        Customer,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='Registered Customer'
    )
    # Fields for guest (anonymous) user orders
    guest_name = models.CharField(verbose_name='Guest Name', max_length=100, null=True, blank=True)
    guest_phone = models.CharField(verbose_name='Guest Phone', max_length=20, null=True, blank=True)

    order_date = models.DateTimeField(verbose_name='Order Date', auto_now_add=True)
    total_amount = models.DecimalField(verbose_name='Total Amount', max_digits=10, decimal_places=2)

    STATUS_CHOICES = [
        ('P', 'Paid'),
        ('U', 'Unpaid')
    ]
    status = models.CharField(verbose_name='Order Status', max_length=1, choices=STATUS_CHOICES, default='U')

    class Meta:
        verbose_name = 'Order'
        verbose_name_plural = 'Orders'
        ordering = ['-order_date']

    def get_customer_display_name(self):
        if self.customer:
            return self.customer.name
        return self.guest_name or "Anonymous User"

    def get_status_display_value(self):
        return dict(self.STATUS_CHOICES).get(self.status, self.status)

    def get_absolute_url(self):
        return reverse('order_detail', args=[self.order_id])

    def __str__(self):
        customer_name = self.get_customer_display_name()
        status_display = self.get_status_display_value()
        return f"Order #{self.order_id} - {customer_name} ({status_display})"


class OrderItem(models.Model):
    order_item_id = models.AutoField(verbose_name='Order Item ID', primary_key=True)
    book = models.ForeignKey(Book, on_delete=models.PROTECT, verbose_name='Book')
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items', verbose_name='Order')
    count = models.PositiveIntegerField(verbose_name='Count', default=1)
    price = models.DecimalField(verbose_name='Price at Order', max_digits=6, decimal_places=2)

    class Meta:
        unique_together = [['order', 'book']]
        verbose_name = 'Order Item'
        verbose_name_plural = 'Order Items'

    def __str__(self):
        return f"{self.count} x {self.book.title} (Order #{self.order.order_id})"


class Cart(models.Model):
    cart_id = models.AutoField(verbose_name='Cart ID', primary_key=True)
    customer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        verbose_name='Customer'
    )
    session_key = models.CharField(verbose_name='Session Key', max_length=40, null=True, blank=True, db_index=True)
    created_at = models.DateTimeField(verbose_name='Created At', auto_now_add=True)
    updated_at = models.DateTimeField(verbose_name='Updated At', auto_now=True)

    class Meta:
        verbose_name = 'Cart'
        verbose_name_plural = 'Carts'
        ordering = ['-created_at']

    def __str__(self):
        if self.customer:
            return f"Cart for {self.customer.name} (ID: {self.cart_id})"
        elif self.session_key:
            return f"Anonymous Cart (Session: {self.session_key[:8]}..., ID: {self.cart_id})"
        return f"Cart (ID: {self.cart_id})"

    @property
    def total_amount(self):
        total = sum(item.subtotal for item in self.items.all() if item.book and item.price_at_addition is not None)
        return total

    @property
    def total_items(self):
        return sum(item.quantity for item in self.items.all())


class CartItem(models.Model):
    cart_item_id = models.AutoField(verbose_name='Cart Item ID', primary_key=True)
    cart = models.ForeignKey(
        Cart,
        on_delete=models.CASCADE,
        related_name='items',
        verbose_name='Cart'
    )
    book = models.ForeignKey(
        Book,
        on_delete=models.CASCADE,
        verbose_name='Book'
    )
    quantity = models.PositiveIntegerField(verbose_name='Quantity', default=1)
    price_at_addition = models.DecimalField(verbose_name='Price at Addition', max_digits=6, decimal_places=2)
    added_at = models.DateTimeField(verbose_name='Added At', auto_now_add=True)

    class Meta:
        unique_together = [['cart', 'book']]
        ordering = ['added_at']
        verbose_name = 'Cart Item'
        verbose_name_plural = 'Cart Items'

    def __str__(self):
        return f"{self.quantity} x {self.book.title} (In Cart {self.cart.cart_id})"

    @property
    def subtotal(self):
        if self.price_at_addition is not None and self.quantity is not None:
            return self.price_at_addition * self.quantity
        return 0