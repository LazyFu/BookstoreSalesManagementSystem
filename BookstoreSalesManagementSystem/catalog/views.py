from decimal import Decimal

from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.utils import timezone

# Create your views here.
from .models import Book, Order, OrderItem, Customer
from django.views import generic


def index(request):
    '''
    View function for home page of site.
    '''
    num_books = Book.objects.all().count()
    num_orders = Order.objects.all().count()

    return render(
        request,
        'index.html',
        context={'num_books': num_books, 'num_orders': num_orders, },
    )


class BookListView(generic.ListView):
    model = Book


class BookDetailView(generic.DetailView):
    model = Book


class OrderListView(generic.ListView):
    model = Order


class OrderDetailView(generic.DetailView):
    model = Order
    template_name = 'catalog/order_detail.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        order = self.get_object()
        items = []

        for item in order.items.all():
            subtotal = item.count * item.price
            items.append({
                'title': item.book.title,
                'count': item.count,
                'price': item.price,
                'subtotal': subtotal,
            })

        context['items'] = items
        context['total'] = order.total_amount
        return context


def add_to_cart(request, isbn):
    try:
        book = Book.objects.get(isbn=isbn)
        quantity = int(request.POST.get('quantity', 1))

        # 直接扣减总库存
        with transaction.atomic():
            if book.stock >= quantity:
                book.stock -= quantity
                book.save()

                # 记录临时售出状态（使用session）
                cart = request.session.get('cart', {})
                cart[book.isbn] = {
                    'quantity': quantity,
                    'expires': timezone.now().timestamp() + 900  # 15分钟过期
                }
                request.session['cart'] = cart
                return JsonResponse({'status': 'success'})

            return JsonResponse({'status': 'error', 'msg': '库存不足'})

    except Exception as e:
        return JsonResponse({'status': 'error', 'msg': str(e)})


def view_cart(request):
    cart = request.session.get('cart', {})
    cart_items = []
    total = 0

    # 转换为可操作对象
    for isbn, item in cart.items():
        book = Book.objects.get(isbn=isbn)
        quantity = item['quantity']
        item_total = book.price * quantity
        cart_items.append({
            'book': book,
            'quantity': quantity,
            'total': item_total
        })
        total += item_total

    return render(request, 'catalog/session_cart.html', {
        'cart_items': cart_items,
        'total': total
    })


def checkout(request):
    cart = request.session.get('cart', {})

    if request.method == 'POST':
        name = request.POST.get('name')
        phone = request.POST.get('phone')
        status = request.POST.get('status', 'U')

        if not name or not phone:
            return render(request, 'catalog/checkout.html', {
                'error': '请填写所有信息',
            })

        # 创建客户
        customer, created = Customer.objects.get_or_create(name=name, phone=phone)

        order = Order.objects.create(customer=customer, total_amount=0, status=status)
        total_amount = Decimal('0.00')

        for isbn, item in cart.items():
            quantity = int(item['quantity'])
            book = Book.objects.get(isbn=isbn)
            price = book.price
            total_price = price * quantity

            OrderItem.objects.create(
                order=order,
                book=book,
                count=quantity,
                price=price
            )

            total_amount += total_price

        order.total_amount = total_amount
        order.save()

        request.session['cart'] = {}

        return redirect(order.get_absolute_url())

    return render(request, 'catalog/checkout.html')


def update_cart(request):
    cart = request.session.get('cart', {})
    for key in request.POST:
        if key.startswith('quantity_'):
            isbn = key.split('_', 1)[1]
            try:
                qty = int(request.POST[key])
                if qty > 0:
                    cart[isbn] = qty
            except ValueError:
                continue
    request.session['cart'] = cart
    return JsonResponse({'status': 'success'})


def clear_cart(request):
    cart = request.session.get('cart', {})

    # 恢复库存
    for isbn, item in cart.items():
        try:
            book = Book.objects.get(isbn=isbn)
            book.stock += item['quantity']
            book.save()
        except Book.DoesNotExist:
            pass

    # 清空session中的购物车
    request.session['cart'] = {}
    return redirect('view_cart')
