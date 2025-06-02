from decimal import Decimal
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import render, redirect
from .forms import *
from .models import Book, Order, OrderItem, Customer, Cart
from django.views import generic

VIP_DISCOUNT_RATE = Decimal('0.9')


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
    template_name = 'catalog/book_list.html'
    context_object_name = 'book_list'

    def get_queryset(self):
        queryset = super().get_queryset()
        query = self.request.GET.get('q')

        if query:
            queryset = queryset.filter(
                Q(title__icontains=query) | Q(author__icontains=query)
            ).distinct()

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['query'] = self.request.GET.get('q', '')
        return context


class BookDetailView(generic.DetailView):
    model = Book


class OrderListView(LoginRequiredMixin, generic.ListView):  # 3. 继承 LoginRequiredMixin
    model = Order
    template_name = 'catalog/order_list.html'  # 明确指定模板名称（好习惯）
    context_object_name = 'order_list'  # 与模板中使用的变量名一致
    paginate_by = 10  # 可选：添加分页，每页显示10条订单

    def get_queryset(self):
        """
        重写此方法，以便只返回当前登录用户的订单。
        """
        user = self.request.user  # 获取当前登录的用户

        try:
            customer_profile = user.customer
            queryset = Order.objects.filter(customer=customer_profile).order_by('-order_date')
        except Customer.DoesNotExist:
            queryset = Order.objects.none()
        except AttributeError:
            queryset = Order.objects.none()

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = '我的订单'  # 可以在 base_generic.html 中使用 {{ page_title }}
        return context


class OrderDetailView(LoginRequiredMixin, generic.DetailView):
    model = Order
    template_name = 'catalog/order_detail.html'  # 确保路径正确
    context_object_name = 'order'

    def get_queryset(self):
        user = self.request.user
        if user.is_staff:
            return Order.objects.all().order_by('-order_date')  # 管理员查看所有，加排序
        try:
            customer = user.customer
            return Order.objects.filter(customer=customer).order_by('-order_date')  # 用户查看自己的，加排序
        except (Customer.DoesNotExist, AttributeError):
            return Order.objects.none()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        order = self.get_object()  # self.object 也一样
        context['page_title'] = f"订单详情 #{order.order_id}"
        # 所有需要的数据都可以通过 {{ order }} 对象及其关联对象在模板中获取
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
    session_cart_dict = request.session.get('cart', {})
    cart_items_for_template = []

    grand_total_original = Decimal('0.00')
    grand_total_effective = Decimal('0.00')

    is_current_user_vip = False
    if request.user.is_authenticated:
        try:
            if hasattr(request.user, 'customer') and request.user.customer and request.user.customer.is_vip:
                is_current_user_vip = True
        except Customer.DoesNotExist:
            pass
        except AttributeError:
            pass

    valid_cart_items_exist = False
    items_to_remove_from_session = []

    for isbn, item_data in list(session_cart_dict.items()):
        try:
            book = Book.objects.get(isbn=isbn)
            quantity = int(item_data.get('quantity', 0))

            if quantity <= 0:
                items_to_remove_from_session.append(isbn)
                continue

            valid_cart_items_exist = True
            original_price_each = book.price
            effective_price_each = original_price_each
            item_has_discount = False

            if is_current_user_vip:
                effective_price_each = (original_price_each * VIP_DISCOUNT_RATE).quantize(Decimal('0.01'))
                item_has_discount = True

            subtotal_original_for_item = original_price_each * quantity
            subtotal_effective_for_item = effective_price_each * quantity

            grand_total_original += subtotal_original_for_item
            grand_total_effective += subtotal_effective_for_item

            cart_items_for_template.append({
                'book': book,
                'quantity': quantity,
                'original_price_each': original_price_each,
                'effective_price_each': effective_price_each,
                'subtotal_effective': subtotal_effective_for_item,
                'item_has_discount': item_has_discount,
            })
        except Book.DoesNotExist:
            messages.warning(request, f"购物车中的书籍 (ISBN: {isbn}) 已不存在，已将其移除。")
            items_to_remove_from_session.append(isbn)
            continue
        except (ValueError, TypeError):
            messages.error(request, f"购物车中书籍 ISBN {isbn} 的数量信息有误，已移除。")
            items_to_remove_from_session.append(isbn)
            continue

    if items_to_remove_from_session:
        cart_modified = False
        current_session_cart = request.session.get('cart', {})
        for isbn_to_remove in items_to_remove_from_session:
            if isbn_to_remove in current_session_cart:
                del current_session_cart[isbn_to_remove]
                cart_modified = True
        if cart_modified:
            request.session['cart'] = current_session_cart
            request.session.modified = True

    vip_discount_applied_on_cart = is_current_user_vip and valid_cart_items_exist and (
            grand_total_effective < grand_total_original)

    discount_amount_for_cart = Decimal('0.00')
    if vip_discount_applied_on_cart:
        discount_amount_for_cart = grand_total_original - grand_total_effective  # <--- 计算优惠金额

    context = {
        'cart_items': cart_items_for_template,
        'total_original': grand_total_original,
        'total_effective': grand_total_effective,
        'is_vip_user': is_current_user_vip,
        'vip_discount_applied_on_cart': vip_discount_applied_on_cart,  # 标记整个购物车是否应用了折扣
        'discount_amount_cart': discount_amount_for_cart,  # <--- 将计算出的优惠金额传递给模板
    }
    return render(request, 'catalog/session_cart.html', context)


def checkout(request):
    cart = get_cart(request)

    if cart is None or not cart.items.exists():  # 或者你的购物车判空逻辑
        messages.info(request, "您的购物车是空的。")
        return redirect('view_cart')  # 假设 'view_cart' 是你的购物车页面URL名称

    if request.method == 'POST':
        form = CheckoutForm(request.POST)
        if form.is_valid():
            cleaned_data = form.cleaned_data
            name = cleaned_data.get('name')
            phone = cleaned_data.get('phone')
            # email_from_form = cleaned_data.get('email') # 如果你在表单中加回了 email 字段
            order_status_from_form = cleaned_data.get('status')

            order_customer = None  # 用于关联已登录用户

            if request.user.is_authenticated:
                try:
                    order_customer = request.user.customer  # Customer 与 User 是 OneToOne
                    # 如果表单中的姓名或电话与已存的不同，则更新 Customer 信息
                    if order_customer.name != name or order_customer.phone != phone:
                        order_customer.name = name
                        order_customer.phone = phone
                        order_customer.save()
                except Customer.DoesNotExist:
                    # 如果认证用户没有 Customer 对象，则为他们创建一个
                    order_customer = Customer.objects.create(user=request.user, name=name, phone=phone)
                except AttributeError:
                    # 一般不应发生，除非 request.user 不是标准的 User 对象或 Customer 关系设置问题
                    # 为安全起见，可以记录此情况，但订单仍可尝试作为游客订单处理（如果 order_customer 为 None）
                    messages.error(request, "处理您的账户信息时发生错误，请联系支持。")
                    # 也可以选择不允许下单：
                    # return render(request, 'catalog/checkout.html', {'form': form, 'cart': cart})

            # ---- 移除了为游客创建账户 (elif create_account:) 的逻辑 ----
            # 现在，如果 request.user.is_authenticated 为 False, order_customer 将保持为 None
            # 订单将作为游客订单处理

            # 如果之前的 form.add_error() 仅用于账户创建，那么这里的 form.errors 检查也可以简化
            # 但保留它以防 CheckoutForm 本身有其他验证可能添加错误
            if form.errors:
                return render(request, 'catalog/checkout.html', {'form': form, 'cart': cart})

            # ---- 创建订单 Order 和订单项 OrderItem ----
            order_original_total = cart.original_total_amount  # 确保 cart 对象有这些属性
            order_final_total = cart.total_amount
            vip_discount_was_applied = cart.is_vip_discount_active

            try:
                with transaction.atomic():
                    new_order = Order(
                        original_total_amount=order_original_total,
                        final_total_amount=order_final_total,
                        status=order_status_from_form,  # 例如 'U'
                        vip_discount_applied=vip_discount_was_applied
                    )

                    if order_customer:  # 如果用户已登录且 Customer 对象存在
                        new_order.customer = order_customer
                        # 对于已登录用户，通常不需要重复存储 guest_name/phone 到订单自身
                        # 但如果你的 Order 模型设计如此，也可以设置
                    else:  # 用户未登录 (游客订单)
                        new_order.guest_name = name
                        new_order.guest_phone = phone
                        # if email_from_form: # 如果表单收集了游客邮箱
                        #     new_order.guest_email = email_from_form

                    new_order.save()

                    for cart_item_db in cart.items.all():  # 假设 cart.items.all() 返回 CartItem 实例
                        OrderItem.objects.create(
                            order=new_order,
                            book=cart_item_db.book,
                            count=cart_item_db.quantity,
                            price=cart_item_db.effective_price_each,  # 确保 CartItem 有这些字段
                            original_unit_price=cart_item_db.price_at_addition
                        )

                    # 订单成功创建后清空购物车
                    # 具体实现方式取决于你的购物车是如何工作的
                    if hasattr(cart, 'items') and hasattr(cart.items, 'all'):  # 如果items是QuerySet
                        cart.items.all().delete()  # 删除购物车中的商品项
                    # 你可能还需要将购物车标记为非活动或删除购物车本身，或清除session中的cart_id
                    # e.g., cart.active = False; cart.save()
                    if 'cart_id' in request.session and not request.user.is_authenticated:
                        # 对于游客，可以考虑清除其session中的cart_id，以便下次访问时获得新购物车
                        del request.session['cart_id']

                messages.success(request, f"订单 #{new_order.order_id} 已成功提交！")  # 假设 Order 有 order_id
                return redirect('order_detail', pk=new_order.order_id)  # 假设 'order_detail' 是订单详情页的URL名
            except Exception as e:
                messages.error(request, f"创建订单过程中发生系统错误: {e}")
                # 记录错误 e
                form.add_error(None, f"订单提交失败，请稍后重试或联系客服。错误: {e}")
                # 重新渲染表单，保留用户已填写的数据和购物车信息

    else:  # GET 请求
        initial_data_for_form = {'status': 'U'}  # 或 Order.PENDING_PAYMENT_STATUS_CONSTANT
        if request.user.is_authenticated:
            try:
                customer = request.user.customer
                initial_data_for_form['name'] = customer.name
                initial_data_for_form['phone'] = customer.phone
                # if hasattr(customer, 'email'): initial_data_for_form['email'] = customer.email
            except Customer.DoesNotExist:
                initial_data_for_form['name'] = request.user.get_full_name() or request.user.username
                # initial_data_for_form['email'] = request.user.email
                initial_data_for_form['phone'] = ""  # User 模型通常没有 phone
            except AttributeError:
                initial_data_for_form['name'] = request.user.get_full_name() or request.user.username
                initial_data_for_form['phone'] = ""

        form = CheckoutForm(initial=initial_data_for_form)

    context = {
        'form': form,
        'cart': cart,
    }
    return render(request, 'catalog/checkout.html', context)  # 你的结账页面模板


def get_cart(request):
    user = request.user
    db_cart = None  # 这将是我们要返回的数据库 Cart 对象
    session_cart_data = request.session.get('cart', {})  # 这是 add_to_cart 等视图操作的 session 字典

    if user.is_authenticated:
        try:
            customer, _ = Customer.objects.get_or_create(user=user, defaults={'name': user.username, 'phone': ''})
            db_cart, cart_created = Cart.objects.get_or_create(customer=customer)
        except Exception as e:  # 更通用的异常捕获，例如处理非 Customer 用户类型
            if not request.session.session_key:
                request.session.create()
            session_key_for_fallback = request.session.session_key
            db_cart, cart_created = Cart.objects.get_or_create(session_key=session_key_for_fallback,
                                                               customer__isnull=True)
    else:  # 匿名用户
        if not request.session.session_key:
            request.session.create()
        session_key = request.session.session_key
        db_cart, cart_created = Cart.objects.get_or_create(session_key=session_key, customer__isnull=True)

    if session_cart_data and db_cart:  # 确保 db_cart 已成功获取或创建
        items_were_merged = False
        with transaction.atomic():  # 使用数据库事务确保数据一致性
            for isbn, item_details in list(session_cart_data.items()):  # 用 list() 复制，以便在循环中删除
                try:
                    book = Book.objects.get(isbn=isbn)
                    quantity_from_session = int(item_details.get('quantity', 0))

                    if quantity_from_session <= 0:
                        # 如果 session 中的数量无效，可以从 session 字典中移除
                        del request.session['cart'][isbn]
                        items_were_merged = True  # 标记 session 有变动
                        continue

                    # 获取或创建数据库 CartItem
                    cart_item_db, item_db_created = db_cart.items.get_or_create(
                        book=book,
                        defaults={
                            'quantity': quantity_from_session,
                            'price_at_addition': book.price  # 记录添加时的价格
                        }
                    )

                    if not item_db_created:
                        cart_item_db.quantity += quantity_from_session  # 改为累加，与 add_to_cart 字典行为一致
                        cart_item_db.price_at_addition = book.price  # 更新价格，以防变动
                        cart_item_db.save()

                    items_were_merged = True

                except Book.DoesNotExist:
                    if isbn in request.session['cart']:
                        del request.session['cart'][isbn]
                    items_were_merged = True  # 标记 session 有变动
                    continue
                except ValueError:  # quantity 转换 int 失败
                    if isbn in request.session['cart']:
                        del request.session['cart'][isbn]
                    items_were_merged = True  # 标记 session 有变动
                    continue

        if items_were_merged:
            # 如果发生了合并或清理，清空原始的 session 字典购物车部分，并标记 session 已修改
            # 实际上，在循环中逐个删除后，这里可以直接设为空字典
            request.session['cart'] = {}  # 清空，因为所有内容都已尝试合并到数据库
            request.session.modified = True

    return db_cart


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
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()  # 保存 User 对象

            # 从验证通过的表单中获取电话号码
            phone_number_from_form = form.cleaned_data.get('phone')

            # ---- 为新用户创建 Customer 对象 ----
            try:
                Customer.objects.create(
                    user=user,
                    name=user.get_full_name() or user.username,
                    phone=phone_number_from_form,
                    vip_status=False
                )
                messages.success(request, "注册成功！已为您创建客户资料，并保存了电话号码。")
            except Exception as e:
                messages.error(request, f"注册成功，但创建客户资料时发生错误，请联系管理员。错误详情: {e}")

            login(request, user)  # 自动登录新注册的用户
            return redirect('index')  # 跳转到首页
        else:
            messages.error(request, "注册失败，请检查您填写的信息是否有误。")
    else:  # GET 请求
        form = CustomUserCreationForm()
    return render(request, 'registration/signup.html', {'form': form})


@login_required
def edit_profile_view(request):
    # 例如：customer = request.user.customer (如果User有customer属性)
    # 或者：customer = get_object_or_404(Customer, user=request.user)

    try:
        # 假设Customer模型有一个user字段关联到Django的User模型
        customer_instance = request.user.customer
    except Customer.DoesNotExist:
        # 处理用户没有关联Customer实例的情况，可能需要创建或给出提示
        # 例如，如果是新用户，可以考虑在这里创建一个关联的Customer实例
        # customer_instance = Customer.objects.create(user=request.user, name=request.user.get_full_name() or request.user.username)
        messages.warning(request, '您的客户资料不存在，可能需要先创建。')
        return redirect('index')

    if request.method == 'POST':
        form = CustomerProfileForm(request.POST, instance=customer_instance)
        if form.is_valid():
            form.save()
            messages.success(request, '您的个人资料已成功更新！')
            return redirect('profile_edit')  # 或其他成功后跳转的页面
    else:
        form = CustomerProfileForm(instance=customer_instance)

    return render(request, 'catalog/profile.html', {'form': form})


def simplified_forgot_password_request_view(request):
    if request.method == 'POST':
        form = UsernameInputForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            # 将用户名存储在 session 中，以便传递给下一个视图
            request.session['reset_password_for_username'] = username
            messages.info(request, f"准备为用户 '{username}' 重置密码。")
            return redirect('simplified_set_new_password')  # 跳转到设置新密码的URL name
    else:
        form = UsernameInputForm()
    return render(request, 'registration/simplified_forgot_password_request.html', {'form': form})


def simplified_set_new_password_view(request):
    username_to_reset = request.session.get('reset_password_for_username')

    if not username_to_reset:
        messages.error(request, "无法处理密码重置请求，请从第一步开始。")
        return redirect('simplified_forgot_password_request')

    try:
        user_to_reset = User.objects.get(username=username_to_reset)
    except User.DoesNotExist:
        messages.error(request, f"用户 '{username_to_reset}' 不存在。")
        if 'reset_password_for_username' in request.session:
            del request.session['reset_password_for_username']
        return redirect('simplified_forgot_password_request')

    if request.method == 'POST':
        form = CustomSetPasswordForm(user_to_reset, request.POST)  # <--- 使用您的自定义表单
        if form.is_valid():
            form.save()
            messages.success(request, f"用户 '{username_to_reset}' 的密码已成功重置。请使用新密码登录。")
            if 'reset_password_for_username' in request.session:
                del request.session['reset_password_for_username']
            return redirect('login')
        else:
            messages.error(request, "设置新密码失败，请检查您输入的内容。")
    else:
        form = CustomSetPasswordForm(user_to_reset)  # <--- 使用您的自定义表单

    context = {
        'form': form,
        'username': username_to_reset
    }
    return render(request, 'registration/simplified_set_new_password.html', context)
