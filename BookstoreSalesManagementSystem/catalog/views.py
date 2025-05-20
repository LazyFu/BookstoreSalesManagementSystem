from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone

# Create your views here.
from .models import Book, Order, OrderItem
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


# def order_detail(request, order_id):
#     order = get_object_or_404(Order, id=order_id)
#     return render(request, 'catalog/order_detail.html', {'order': order})
#
#
# def book_detail(request, isbn):
#     book = get_object_or_404(Book, id=isbn)
#     return render(request, 'catalog/book_detail.html', {'book': book})

# def add_to_cart(request, isbn):
#     book = get_object_or_404(Book, isbn=isbn)
#     cart = request.session.get('cart', {})
#
#     # 获取用户输入数量（示例）
#     quantity = int(request.POST.get('quantity', 1))
#
#     # 库存校验
#     if book.stock < (cart.get(str(book.isbn), 0) + quantity):
#         return JsonResponse({'status': 'error', 'message': '库存不足'})
#
#     # 更新购物车
#     cart[str(book.isbn)] = cart.get(str(book.isbn), 0) + quantity
#     request.session['cart'] = cart
#
#     return JsonResponse({'status': 'success', 'cart_total': sum(cart.values())})

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

    with transaction.atomic():
        order = Order.objects.create(
            customer=request.user.customer,
            total=0  # 需计算真实金额
        )

        for isbn, qty in cart.items():
            book = Book.objects.select_for_update().get(id=isbn)
            # 创建订单项
            OrderItem.objects.create(
                order=order,
                book=book,
                quantity=qty,
                price=book.price  # 冻结价格
            )
            # 更新库存
            book.stock -= qty
            book.save()

        # 清空购物车
        del request.session['cart']
        request.session.modified = True

    return redirect(order.get_absolute_url())

def remove_from_cart(request, isbn):
    cart = request.session.get('cart', {})
    if isbn in cart:
        cart.pop(isbn)
        request.session['cart'] = cart
        return JsonResponse({'status': 'success'})
    return JsonResponse({'status': 'error', 'message': '未找到该商品'})

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

def update_cart_item(request, isbn):
    quantity = int(request.GET.get('quantity', 1))
    cart = request.session.get('cart', {})
    if quantity > 0:
        cart[isbn] = quantity
        request.session['cart'] = cart
        return JsonResponse({'status': 'success'})
    else:
        return JsonResponse({'status': 'error', 'message': '数量必须大于 0'})


def clear_cart(request):
    request.session['cart'] = {}
    return redirect('view_cart')