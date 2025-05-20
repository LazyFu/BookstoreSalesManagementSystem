# catalog/management/commands/restore_stock.py
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.contrib.sessions.models import Session
from catalog.models import Book


class Command(BaseCommand):
    help = '恢复过期库存'

    def handle(self, *args, **options):
        expired_time = timezone.now() - timezone.timedelta(minutes=15)
        sessions = Session.objects.filter(expire_date__gte=timezone.now())

        for session in sessions:
            session_data = session.get_decoded()
            cart = session_data.get('cart', {})

            for isbn, item in list(cart.items()):
                if item['lock_time'] < expired_time.timestamp():
                    try:
                        book = Book.objects.get(isbn=isbn)
                        book.stock += item['quantity']
                        book.save()
                        del cart[isbn]
                        session.session_data = session_data
                        session.save()
                    except Exception as e:
                        self.stdout.write(f"错误：{e}")