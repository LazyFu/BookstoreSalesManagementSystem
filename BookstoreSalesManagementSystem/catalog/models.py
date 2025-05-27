from django.contrib.auth.models import User
from django.db import models
from django.urls import reverse


# Create your models here.
class Book(models.Model):
    isbn = models.CharField('ISBN', max_length=13,
                            help_text='13 Character <a href="https://www.isbn-international.org/content/what-isbn">ISBN number</a>',
                            primary_key=True)
    title = models.CharField('Title', max_length=100)
    author = models.CharField('Author', max_length=100, null=True)
    press = models.CharField('Press', max_length=100, null=True)
    price = models.DecimalField('Price', decimal_places=2, max_digits=6)  # 四位加两位小数
    stock = models.PositiveIntegerField('Stock', default=0)
    summary = models.TextField('Summary', max_length=1000, blank=True, null=True)

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse('book_detail', args=[str(self.isbn)])


class Customer(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, primary_key=True, verbose_name='用户')
    # customer_id = models.AutoField(primary_key=True, verbose_name='Customer ID')
    name = models.CharField('Name', max_length=100)
    phone = models.CharField('Phone', max_length=11)

    def __str__(self):
        return self.user.username


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

    def get_absolute_url(self):
        return reverse('order_detail', args=[self.order_id])

    def __str__(self):
        return f"Order #{self.order_id} - {self.customer.name} ({self.get_status_display()})"


class OrderItem(models.Model):
    order_item_id = models.AutoField(primary_key=True, verbose_name='Order Item ID')
    book = models.ForeignKey(Book, on_delete=models.PROTECT)
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    count = models.PositiveIntegerField('Order Count', default=1)
    price = models.DecimalField('Price', decimal_places=2, max_digits=6)

    class Meta:
        unique_together = [['order', 'book']]

    def __str__(self):
        return f"{self.count} x {self.book.title} in Order #{self.order.order_id}"


class Cart(models.Model):
    cart_id = models.AutoField(primary_key=True, verbose_name='购物车ID')
    # 如果你的系统有登录用户，可以关联到Django的User模型或你的Customer模型
    # 这里我们关联到你的Customer模型，并允许匿名购物车
    customer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,  # 如果客户被删除，其购物车也一并删除
        null=True,  # 允许匿名用户的购物车 (customer字段可以为空)
        blank=True,  # 在表单中也允许为空
        verbose_name='顾客'
    )
    # 用于匿名用户的会话密钥，方便找回他们的购物车
    session_key = models.CharField('会话密钥', max_length=40, null=True, blank=True, db_index=True)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    def __str__(self):
        if self.customer:
            return f"顾客 {self.customer.name} 的购物车 (ID: {self.cart_id})"
        elif self.session_key:
            return f"匿名购物车 (Session: {self.session_key[:8]}..., ID: {self.cart_id})"
        return f"购物车 (ID: {self.cart_id})"

    @property
    def total_amount(self):
        """计算购物车中所有商品的总价"""
        return sum(item.subtotal for item in self.items.all())

    @property
    def total_items(self):
        """计算购物车中所有商品的总数量"""
        return sum(item.quantity for item in self.items.all())


class CartItem(models.Model):
    cart_item_id = models.AutoField(primary_key=True, verbose_name='购物车项ID')
    cart = models.ForeignKey(
        Cart,
        on_delete=models.CASCADE,  # 如果购物车被删除，其所有项也一并删除
        related_name='items',  # 方便从Cart对象反向查询 Cart.items.all()
        verbose_name='购物车'
    )
    book = models.ForeignKey(
        Book,
        on_delete=models.CASCADE,  # 如果书籍被删除（或下架），购物车中的对应项也删除
        # 或者可以考虑用 on_delete=models.SET_NULL 并处理这种情况
        verbose_name='书籍'
    )
    quantity = models.PositiveIntegerField('数量', default=1)
    # 记录加入购物车时的价格，以防止后续书籍价格变动影响已在购物车的商品
    price_at_addition = models.DecimalField('加入时价格', decimal_places=2, max_digits=6)
    added_at = models.DateTimeField('添加时间', auto_now_add=True)

    class Meta:
        # 同一个购物车内，同一本书籍只能有一条记录，通过数量来控制
        unique_together = [['cart', 'book']]
        ordering = ['added_at']  # 默认按添加时间排序

    def __str__(self):
        return f"{self.quantity} x {self.book.title} (在购物车 {self.cart.cart_id})"

    @property
    def subtotal(self):
        """计算该购物车项的小计（价格 * 数量）"""
        return self.price_at_addition * self.quantity
