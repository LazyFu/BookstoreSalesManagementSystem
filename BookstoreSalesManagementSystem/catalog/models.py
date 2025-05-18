from django.db import models
from django.urls import reverse


# Create your models here.
class Book(models.Model):
    isbn = models.CharField('ISBN', max_length=13,
                            help_text='13 Character <a href="https://www.isbn-international.org/content/what-isbn">ISBN number</a>',
                            primary_key=True)
    title = models.CharField('Title', max_length=100)
    author = models.CharField('Author', max_length=100)
    press = models.CharField('Press', max_length=100)
    price = models.DecimalField('Price', decimal_places=2, max_digits=6)  # 四位加两位小数
    stock = models.IntegerField('Stock', default=0)
    summary = models.TextField('Summary', max_length=1000)

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse('book-detail', args=[str(self.isbn)])


class Customer(models.Model):
    customer_id = models.AutoField(primary_key=True, verbose_name='Customer ID')
    first_name = models.CharField('First Name', max_length=100)
    name = models.CharField('Name', max_length=100)
    phone = models.CharField('Phone', max_length=11)

    def __str__(self):
        return self.name


class Order(models.Model):
    order_id = models.AutoField(primary_key=True, verbose_name='Order ID')
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT)
    order_date = models.DateTimeField('Order Date', auto_now_add=True)
    total_amount = models.DecimalField('Total Amount', decimal_places=2, max_digits=10)
    STATUS_CHOICES = [('P', 'Paid'), ('U', 'Unpaid')]
    status = models.CharField('Order Status', max_length=1, choices=STATUS_CHOICES, default='U')

    def get_status_display(self):
        if self.status == 'P':
            return 'Paid'
        else:
            return 'Unpaid'

    def __str__(self):
        return f"Order #{self.order_id} - {self.customer.name} ({self.get_status_display()})"


class OrderItem(models.Model):
    order_item_id = models.AutoField(primary_key=True, verbose_name='Order Item ID')
    book = models.ForeignKey(Book, on_delete=models.PROTECT)
    order = models.ForeignKey(Order, on_delete=models.PROTECT)
    count = models.IntegerField('Order Count', default=1)
    price = models.DecimalField('Price', decimal_places=2, max_digits=6)

    class Meta:
        unique_together = [['order', 'book']]

    def __str__(self):
        return f"{self.count} x {self.book.title} in Order #{self.order.order_id}"
