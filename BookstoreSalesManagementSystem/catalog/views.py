from django.contrib.auth import login
from django.contrib.auth.models import User
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import render, redirect
from .forms import CustomUserCreationForm, CheckoutForm
# Create your views here.
from .models import Book, Order, OrderItem, Customer, Cart
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
    cart = get_cart(request)
    if cart is None or not cart.items.exists():
        # messages.info(request, "您的购物车是空的。")
        return redirect('view_cart')

    if request.method == 'POST':
        form = CheckoutForm(request.POST)
        if form.is_valid():
            cleaned_data = form.cleaned_data
            name = cleaned_data.get('name')
            phone = cleaned_data.get('phone')
            email = cleaned_data.get('email')
            password = cleaned_data.get('password')
            create_account = cleaned_data.get('create_account')

            order_customer = None
            # new_user_created = False # 移到 try 块内部或作为 User 对象是否创建的标志

            if request.user.is_authenticated:
                try:
                    order_customer = request.user.customer
                    # （可选）如果表单中的信息与已存信息不同，是否更新 Customer 对象？
                    if order_customer.name != name or order_customer.phone != phone:
                        order_customer.name = name
                        order_customer.phone = phone
                        order_customer.save()
                except Customer.DoesNotExist:  # 已认证用户但无Customer对象 (罕见，但需处理)
                    # messages.warning(request, "无法找到您的顾客资料，将作为访客下单。")
                    pass  # 或者在这里为已认证用户创建Customer
                except AttributeError:  # e.g. superuser without customer
                    pass


            elif create_account:  # 仅当勾选了创建账户并且表单验证通过（包括邮箱和密码的必填）
                try:
                    new_user = User.objects.create_user(username=email, email=email, password=password)
                    # 你可以在这里设置 new_user.first_name, new_user.last_name 等
                    order_customer = Customer.objects.create(user=new_user, name=name, phone=phone)
                    login(request, new_user)  # 创建并登录
                    # messages.success(request, "账户创建成功并已自动登录！")
                except Exception as e:  # 更具体的异常捕获更好
                    # messages.error(request, f"创建账户时发生错误: {e}")
                    # 这种情况下，错误应该由表单的 clean_email 捕获，这里是备用
                    # 或者，如果错误不是由表单验证捕获的（例如数据库问题）
                    # 重新渲染表单，可能需要添加一个通用错误到表单
                    form.add_error(None, f"创建账户过程中发生系统错误: {e}")
                    return render(request, 'catalog/checkout.html', {'form': form, 'cart': cart})

            # ---- 创建订单 Order 和订单项 OrderItem ----
            total_amount = cart.total_amount

            new_order = Order(total_amount=total_amount, status='U')

            if order_customer:
                new_order.customer = order_customer
            else:  # 匿名访客订单 (未登录且未选择创建账户)
                new_order.guest_name = name
                new_order.guest_phone = phone

            new_order.save()

            for cart_item in cart.items.all():
                OrderItem.objects.create(
                    order=new_order,
                    book=cart_item.book,
                    count=cart_item.quantity,
                    price=cart_item.price_at_addition
                )

            # 清空购物车逻辑 (示例)
            if hasattr(cart, 'items') and cart.items.exists():  # 确保 cart.items 存在
                cart.items.all().delete()
            # 或者如果Cart对象本身是基于session并且不再需要，可以考虑删除Cart对象
            # if not request.user.is_authenticated and cart.customer is None:
            #     try:
            #         del request.session['cart_id'] # 假设你用 cart_id 存在 session 中
            #     except KeyError:
            #         pass
            #     cart.delete()

            # messages.success(request, f"订单 #{new_order.order_id} 已成功提交！")
            return redirect('order_detail', pk=new_order.order_id)  # 假设你有这个URL name

        # else: 表单验证失败，会自动进入下面的render，form对象已包含错误信息

    else:  # GET 请求
        initial_data_for_form = {}
        if request.user.is_authenticated:
            try:
                customer = request.user.customer
                initial_data_for_form['name'] = customer.name
                initial_data_for_form['phone'] = customer.phone
                initial_data_for_form['email'] = request.user.email
            except Customer.DoesNotExist:
                initial_data_for_form['name'] = request.user.get_full_name() or request.user.username
                initial_data_for_form['email'] = request.user.email
            except AttributeError:  # e.g. superuser
                initial_data_for_form['name'] = request.user.get_full_name() or request.user.username
                initial_data_for_form['email'] = request.user.email
        form = CheckoutForm(initial=initial_data_for_form)

    context = {
        'form': form,  # 将表单实例传递给模板
        'cart': cart,
        # 'form_name': initial_form_data.get('name', ''), # 这些不再需要，由表单处理
        # 'form_phone': initial_form_data.get('phone', ''),
        # 'form_email': initial_form_data.get('email', ''),
    }
    return render(request, 'catalog/checkout.html', context)


# 辅助函数：获取购物车 (你需要根据你的实现来编写)
def get_cart(request):
    cart_id = request.session.get('cart_id')
    if request.user.is_authenticated:
        try:
            customer = request.user.customer
            cart, created = Cart.objects.get_or_create(customer=customer, defaults={
                'session_key': request.session.session_key if not request.session.session_key else None})
            # 如果用户登录了，并且session中有一个匿名购物车，你可能还想合并它们
            if created and cart_id:
                try:
                    session_cart = Cart.objects.get(id=cart_id, customer__isnull=True)
                    # 合并逻辑...
                except Cart.DoesNotExist:
                    pass

        except Customer.DoesNotExist:  # 用户已认证但没有Customer对象
            cart, created = Cart.objects.get_or_create(
                session_key=request.session.session_key or request.session.create())
            if created and not request.session.session_key:
                request.session['cart_id'] = cart.cart_id
        except AttributeError:  # 例如超级用户
            cart, created = Cart.objects.get_or_create(
                session_key=request.session.session_key or request.session.create())

    else:  # 匿名用户
        if not request.session.session_key:
            request.session.create()
        session_key = request.session.session_key
        cart, created = Cart.objects.get_or_create(session_key=session_key, customer__isnull=True)
        if created:
            request.session['cart_id'] = cart.cart_id

    return cart


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


def signup_view(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)  # 使用自定义表单
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('index')  # 修改为你的首页 URL name
    else:
        form = CustomUserCreationForm()  # 使用自定义表单
    return render(request, 'registration/signup.html', {'form': form})
