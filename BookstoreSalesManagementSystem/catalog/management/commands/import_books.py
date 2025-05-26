# import_books.py
import json
from django.core.management.base import BaseCommand
from django.utils.translation.trans_real import catalog

from catalog.models import Book


class Command(BaseCommand):
    help = 'Import books from a JSON file into the database'

    def add_arguments(self, parser):
        parser.add_argument('json_file', type=str, help='Path to the JSON file')

    def handle(self, *args, **kwargs):
        json_file_path = kwargs['json_file']

        try:
            with open(json_file_path, 'r', encoding='utf-8') as file:
                books_data = json.load(file)
                for data in books_data:
                    # 清洗价格字段（移除"元"并转为数字）
                    price_str = data.get('price', '0').replace('元', '').strip()
                    try:
                        price = float(price_str)
                    except ValueError:
                        price = 0.0  # 默认值处理异常价格

                    # 创建或更新书籍（根据ISBN唯一性）
                    Book.objects.update_or_create(
                        isbn=data['isbn'],  # 用于查找或创建的键
                        defaults={
                            'title': data['title'],
                            'summary': data.get('summary', '无'),
                            'author': data.get('author', '佚名'),
                            'press': data.get('press', '无名出版社'),
                            'price': price,
                            'stock': data['stock'],
                        }
                    )
                    self.stdout.write(self.style.SUCCESS(f'Successfully imported: {data["title"]}'))
        except FileNotFoundError:
            self.stdout.write(self.style.ERROR('JSON file not found!'))
        except KeyError as e:
            self.stdout.write(self.style.ERROR(f'Missing key in JSON data: {e}'))
