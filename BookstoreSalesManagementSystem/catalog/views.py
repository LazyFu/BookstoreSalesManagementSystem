from django.shortcuts import render, get_object_or_404

# Create your views here.
from .models import Book, Order
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

