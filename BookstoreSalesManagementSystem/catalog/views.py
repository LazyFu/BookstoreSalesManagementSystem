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


# def checkout(request):
#     cart = request.session.get('cart', {})
#
#     if request.method == 'POST':
#         name = request.POST.get('name')
#         phone = request.POST.get('phone')
#         status = request.POST.get('status', 'U')
#
#         if not name or not phone:
#             return render(request, 'catalog/checkout.html', {
#                 'error': '请填写所有信息',
#             })
#
#         # 创建客户
#         customer, created = Customer.objects.get_or_create(name=name, phone=phone)
#
#         order = Order.objects.create(customer=customer, total_amount=0, status=status)
#         total_amount = Decimal('0.00')
#
#         for isbn, item in cart.items():
#             quantity = int(item['quantity'])
#             book = Book.objects.get(isbn=isbn)
#             price = book.price
#             total_price = price * quantity
#
#             OrderItem.objects.create(
#                 order=order,
#                 book=book,
#                 count=quantity,
#                 price=price
#             )
#
#             total_amount += total_price
#
#         order.total_amount = total_amount
#         order.save()
#
#         request.session['cart'] = {}
#
#         return redirect(order.get_absolute_url())
#
#     return render(request, 'catalog/checkout.html')

def checkout(request):
    form_name_initial = ''
    form_phone_initial = ''
    # form_address_initial = '' # 如果有地址字段

    if request.user.is_authenticated:
        try:
            # 尝试从关联的 Customer 模型获取信息
            customer = request.user.customer
            form_name_initial = customer.name
            form_phone_initial = customer.phone
            # form_address_initial = customer.address # 如果有地址字段
        except Customer.DoesNotExist:
            # 如果没有 Customer 关联对象，尝试从 User 对象获取
            form_name_initial = request.user.get_full_name()
            if not form_name_initial:  # 如果全名为空
                form_name_initial = request.user.username  # 使用用户名作为备选
            # form_phone_initial 和 form_address_initial 保持为空，除非 User 模型也有这些信息
        except AttributeError:  # 例如，超级用户可能没有 customer 属性
            form_name_initial = request.user.get_full_name() or request.user.username

    if request.method == 'POST':
        # 获取用户提交的数据
        name_from_form = request.POST.get('name')
        phone_from_form = request.POST.get('phone')
        status_from_form = request.POST.get('status', 'U')  # 安全起见，若未提交则默认为'U'

        # ---- 处理顾客信息 ----
        current_customer_for_order = None
        if request.user.is_authenticated:
            try:
                current_customer_for_order = request.user.customer
                # （可选）如果表单中的信息与已存信息不同，是否更新 Customer 对象？
                # if current_customer_for_order.name != name_from_form or current_customer_for_order.phone != phone_from_form:
                #     current_customer_for_order.name = name_from_form
                #     current_customer_for_order.phone = phone_from_form
                #     current_customer_for_order.save()
            except (Customer.DoesNotExist, AttributeError):
                # 如果认证用户没有Customer对象，你可能需要决定是否在这里创建一个
                # 或者，如果Order.customer可以为null，并且你直接在Order上存name/phone
                pass  # 留给你根据你的具体业务逻辑决定
        # else: # 匿名用户
        # 你提到匿名用户结算已实现。
        # 这里需要你现有的逻辑来处理匿名用户的顾客信息，
        # 可能是创建一个临时的Customer（如果模型允许user为null），
        # 或者直接将 name_from_form, phone_from_form 用于创建Order。

        # ---- 创建订单 Order 和订单项 OrderItem 的逻辑 ----
        # 1. 获取购物车
        # 2. 计算总金额
        # 3. 创建 Order 对象:
        #    - customer: current_customer_for_order (如果已登录且找到) 或 None/其他 (如果匿名)
        #    - total_amount: 计算得到的总金额
        #    - status: 强烈建议在这里将 status 设为 'U'，而不是直接使用 status_from_form，除非你有特殊理由。
        #      new_order_status = 'U' # 总是以未支付开始
        #    - 如果是匿名用户，你可能还需要在Order对象上直接保存姓名和电话。
        #      (例如, Order模型可能有 guest_name, guest_phone 字段，
        #      或者 Order.customer 可以为 null，此时这些信息必须存储)
        #
        # new_order = Order.objects.create(
        #     customer=current_customer_for_order,
        #     total_amount=cart_total,
        #     status='U', # 推荐
        #     # 如果Order模型需要直接存储匿名用户信息：
        #     # guest_name=name_from_form if not request.user.is_authenticated else None,
        #     # guest_phone=phone_from_form if not request.user.is_authenticated else None,
        # )
        #
        # 4. 为购物车中的每个商品创建 OrderItem 对象，并关联到 new_order
        # 5. 清空购物车
        # 6. 重定向到订单成功页面或支付页面
        # return redirect('order_success_or_payment_url')
        pass  # 此处替换为你的实际订单处理逻辑

    # 准备传递给模板的上下文
    context = {
        'form_name': form_name_initial,
        'form_phone': form_phone_initial,
        # 'form_address': form_address_initial,
        # 'cart_items': ...,
        # 'cart_total_amount': ...,
    }
    return render(request, 'catalog/checkout.html', context)


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
