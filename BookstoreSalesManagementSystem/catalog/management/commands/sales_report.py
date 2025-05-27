import os
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta, datetime
from django.db.models import Sum, F, ExpressionWrapper, DecimalField
from decimal import Decimal
from django.conf import settings  # 用于可能的路径配置

# 假设您的模型在 catalog 应用中
from catalog.models import Book, Order, OrderItem, Customer


# --- 辅助函数：计算日期范围 ---
def get_previous_full_month_range():
    today = timezone.now().date()
    first_day_current_month = today.replace(day=1)
    last_day_previous_month = first_day_current_month - timedelta(days=1)
    first_day_previous_month = last_day_previous_month.replace(day=1)
    return first_day_previous_month, last_day_previous_month


def get_last_n_days_range(n_days):
    today = timezone.now().date()  # 报告截止到今天（含）
    start_date = today - timedelta(days=n_days - 1)
    return start_date, today


class Command(BaseCommand):
    help = '生成销售报告，并将其导出到文本文件。报告包含上个月和过去7天的销售数据，以及历史顾客消费排行。'

    def add_arguments(self, parser):
        parser.add_argument(
            '--output_dir',
            type=str,
            default='sales_reports',  # 默认保存在项目根目录下的 sales_reports 文件夹
            help='指定保存报告文件的目录。默认为 "sales_reports"。'
        )
        parser.add_argument(
            '--filename_prefix',
            type=str,
            default='sales_report',
            help='指定报告文件名的前缀。默认为 "sales_report"。'
        )
        parser.add_argument(
            '--quiet',
            action='store_true',  # 如果提供此参数，则为 True
            help='禁止在控制台输出报告内容（仍会输出文件保存路径和错误）。'
        )

    def _generate_lines_for_period_stats(self, start_date, end_date, period_name, top_n_books=10):
        """生成指定周期销售统计的文本行列表 (无样式)"""
        lines = []
        lines.append(f"\n--- {period_name}销售统计 ({start_date} 至 {end_date}) ---")
        lines.append(f" (书籍销量排行 Top {top_n_books})")

        datetime_start = timezone.make_aware(datetime.combine(start_date, datetime.min.time())) if start_date else None
        datetime_end = timezone.make_aware(datetime.combine(end_date, datetime.max.time())) if end_date else None

        paid_orders_filter_kwargs = {'order__status': 'P'}
        if datetime_start: paid_orders_filter_kwargs['order__order_date__gte'] = datetime_start
        if datetime_end: paid_orders_filter_kwargs['order__order_date__lte'] = datetime_end

        base_query = OrderItem.objects.filter(**paid_orders_filter_kwargs)

        # 1. 书籍按销量（数量）排序
        lines.append(f"\n1. {period_name} 书籍销量排行 (Top {top_n_books} 按售出数量):")
        books_by_sales_quantity = base_query \
            .values('book__title', 'book__isbn') \
            .annotate(total_quantity_sold=Sum('count')) \
            .order_by('-total_quantity_sold', 'book__title')

        if books_by_sales_quantity.exists():
            for rank, item in enumerate(books_by_sales_quantity[:top_n_books], 1):
                lines.append(
                    f"  {rank}. 《{item['book__title']}》(ISBN: {item['book__isbn']}) - 销量: {item['total_quantity_sold']}")
        else:
            lines.append(f"  在“{period_name}”内无书籍销售记录。")

        # 2. 总体销售情况
        lines.append(f"\n2. {period_name} 总体销售情况:")
        overall_sales_data = base_query \
            .aggregate(
            grand_total_revenue=Sum(ExpressionWrapper(F('count') * F('price'), output_field=DecimalField())),
            grand_total_quantity=Sum('count')
        )
        grand_total_revenue = overall_sales_data.get('grand_total_revenue') or Decimal('0.00')
        grand_total_quantity = overall_sales_data.get('grand_total_quantity') or 0

        lines.append(f"  总销售额: ¥{grand_total_revenue:.2f}")
        lines.append(f"  总销售数量: {grand_total_quantity} 本")

        if books_by_sales_quantity.exists():
            top_book_info = books_by_sales_quantity.first()
            if top_book_info:
                top_book_isbn = top_book_info['book__isbn']
                top_book_revenue_data = base_query.filter(book__isbn=top_book_isbn) \
                    .aggregate(revenue=Sum(ExpressionWrapper(F('count') * F('price'), output_field=DecimalField())))
                top_book_revenue = top_book_revenue_data.get('revenue') or Decimal('0.00')
                lines.append(
                    f"  {period_name}销量冠军书籍 (按数量): 《{top_book_info['book__title']}》, 销量: {top_book_info['total_quantity_sold']}, 其销售额: ¥{top_book_revenue:.2f}")
        else:
            lines.append(f"  {period_name}销量冠军书籍: 无销售记录")
        return lines

    def _generate_lines_for_top_customers(self, limit=5):
        """生成历史顾客消费排行文本行列表 (无样式)"""
        lines = []
        lines.append(f"\n\n=== 历史顾客消费总额排行 (Top {limit}) ===")
        top_customers_query = Order.objects.filter(status='P', customer__isnull=False) \
            .values('customer__name', 'customer__user__username') \
            .annotate(total_spent=Sum('final_total_amount')) \
            .order_by('-total_spent')

        if top_customers_query.exists():
            for rank, cust_data in enumerate(top_customers_query[:limit], 1):
                name = cust_data.get('customer__name') or "N/A"
                username = cust_data.get('customer__user__username') or "N/A"
                total_spent = cust_data.get('total_spent') or Decimal('0.00')
                lines.append(f"  {rank}. {name} (用户名: {username}) - 总消费: ¥{total_spent:.2f}")
        else:
            lines.append("  无顾客消费数据（或所有订单均为访客订单）。")
        return lines

    def handle(self, *args, **options):
        output_dir_path = options['output_dir']
        filename_prefix = options['filename_prefix']
        is_quiet = options['quiet']

        # 确保输出目录存在
        if not os.path.isabs(output_dir_path):  # 如果不是绝对路径，则基于项目根目录
            output_dir_path = os.path.join(settings.BASE_DIR, output_dir_path)
        os.makedirs(output_dir_path, exist_ok=True)

        # 生成文件名
        timestamp_str = timezone.now().strftime("%Y%m%d_%H%M%S")
        report_filename = f"{filename_prefix}_{timestamp_str}.txt"
        report_filepath = os.path.join(output_dir_path, report_filename)

        all_report_lines = []  # 存储所有报告文本行

        if not is_quiet:
            self.stdout.write(self.style.SUCCESS("开始生成销售报告..."))
        all_report_lines.append("销售报告")
        all_report_lines.append(f"生成时间: {timezone.now().strftime('%Y-%m-%d %H:%M:%S %Z')}")
        all_report_lines.append("==============================================")

        # 报告1: 上一个完整月份
        last_month_start, last_month_end = get_previous_full_month_range()
        all_report_lines.extend(
            self._generate_lines_for_period_stats(last_month_start, last_month_end, "上一个完整月份", top_n_books=10)
        )

        # 报告2: 过去7天
        last_7_days_start, last_7_days_end = get_last_n_days_range(7)
        all_report_lines.extend(
            self._generate_lines_for_period_stats(last_7_days_start, last_7_days_end, "过去7天", top_n_books=10)
        )

        # 报告3: 历史顾客消费排行
        all_report_lines.extend(
            self._generate_lines_for_top_customers(limit=5)
        )
        all_report_lines.append("\n==============================================")
        all_report_lines.append("报告结束")

        # 如果不是 quiet 模式，打印到控制台 (带样式)
        if not is_quiet:
            self.stdout.write(self.style.SUCCESS("\n--- 控制台报告预览 ---"))
            # 为了在控制台有样式，我们可以选择性地应用 self.style
            # 但为了简化，这里直接打印收集到的纯文本行
            for line in all_report_lines:
                # 对于标题行，可以尝试应用样式
                if "---" in line or "===" in line:
                    self.stdout.write(self.style.HTTP_INFO(line))
                elif "销量排行" in line or "总体销售情况" in line or "顾客消费总额排行" in line:
                    self.stdout.write(self.style.SQL_COLTYPE(line))
                else:
                    self.stdout.write(line)
            self.stdout.write(self.style.SUCCESS("--- 报告预览结束 ---"))

        # 将所有收集到的文本行写入文件
        try:
            with open(report_filepath, 'w', encoding='utf-8') as f:
                for line in all_report_lines:
                    f.write(line + '\n')

            # 无论是否 quiet, 都告知用户文件已保存
            success_msg = f"\n报告已成功保存到: {report_filepath}"
            self.stdout.write(self.style.SUCCESS(success_msg) if not is_quiet else success_msg)

        except IOError as e:
            error_msg = f"\n错误：无法将报告写入文件 {report_filepath}: {e}"
            self.stderr.write(self.style.ERROR(error_msg) if not is_quiet else error_msg)