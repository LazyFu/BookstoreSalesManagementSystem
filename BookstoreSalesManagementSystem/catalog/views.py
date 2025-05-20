from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404, redirect

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
# def book_detail(request, book_id):
#     book = get_object_or_404(Book, id=book_id)
#     return render(request, 'catalog/book_detail.html', {'book': book})

# views.py
def add_to_cart(request, book_id):
    book = get_object_or_404(Book, pk=book_id)
    cart = request.session.get('cart', {})

    # 获取用户输入数量（示例）
    quantity = int(request.POST.get('quantity', 1))

    # 库存校验
    if book.stock < (cart.get(str(book.id), 0) + quantity):
        return JsonResponse({'status': 'error', 'message': '库存不足'})

    # 更新购物车
    cart[str(book.id)] = cart.get(str(book.id), 0) + quantity
    request.session['cart'] = cart

    return JsonResponse({'status': 'success', 'cart_total': sum(cart.values())})


def view_cart(request):
    cart = request.session.get('cart', {})
    cart_items = []
    total = 0

    # 转换为可操作对象
    for book_id, qty in cart.items():
        book = Book.objects.get(id=int(book_id))
        item_total = book.price * qty
        cart_items.append({
            'book': book,
            'quantity': qty,
            'total': item_total
        })
        total += item_total

    return render(request, 'cart/session_cart.html', {
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

        for book_id, qty in cart.items():
            book = Book.objects.select_for_update().get(id=book_id)
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