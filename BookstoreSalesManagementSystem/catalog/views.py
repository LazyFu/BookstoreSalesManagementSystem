from decimal import Decimal
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import render, redirect

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
    if request.method == 'POST':  # 确保是 POST 请求
        try:
            book = Book.objects.get(isbn=isbn)
            quantity = int(request.POST.get('quantity', 1))

            # 直接扣减总库存
            with transaction.atomic():
                if book.stock >= quantity:
                    book.stock -= quantity
                    book.save()  # 保存更新后的库存

                    cart = request.session.get('cart', {})
                    cart_item = cart.get(book.isbn, {'quantity': 0})
                    cart_item['quantity'] += quantity

                    cart[book.isbn] = cart_item
                    request.session['cart'] = cart

                    # 在成功的响应中返回新的库存数量
                    return JsonResponse({'status': 'success', 'new_stock': book.stock,
                                         'cart_total_items': sum(item['quantity'] for item in cart.values())})
                else:
                    return JsonResponse({'status': 'error', 'msg': '库存不足'})
        except Book.DoesNotExist:
            return JsonResponse({'status': 'error', 'msg': '书籍不存在'})
        except ValueError:  # 处理 quantity 不是有效数字的情况
            return JsonResponse({'status': 'error', 'msg': '无效的数量'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'msg': '处理请求时发生错误'})
    return JsonResponse({'status': 'error', 'msg': '无效的请求方法'}, status=405)


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
