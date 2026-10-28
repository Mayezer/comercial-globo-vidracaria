from calendar import monthrange
from datetime import date, datetime
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models.deletion import ProtectedError
from django.db.models import Count, Q, Sum
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.formats import date_format
from django.views.decorators.http import require_POST

from accounts.models import Profile, normalize_text, only_digits
from app.crypto import blind_index
from categories.models import Category
from products.models import Product, ProductStockExit
from glazing_services.models import Service

from .decorators import staff_required, superuser_required
from .forms import (
    AdministratorCreationForm,
    AdministratorUpdateForm,
    CashTransactionForm,
    CategoryManagementForm,
    CustomerManagementForm,
    EmployeeForm,
    ExpenseForm,
    PayrollForm,
    ProductManagementForm,
    ProductStockExitForm,
    QuoteRequestForm,
    ServiceManagementForm,
    SupplierForm,
    SystemSettingsForm,
)
from .models import (
    CashTransaction,
    Employee,
    Expense,
    Payroll,
    QuoteAdminNotification,
    QuoteRequest,
    QuoteStatusHistory,
    Supplier,
    SystemSettings,
)
from .pdf import build_text_pdf


User = get_user_model()


def _date_from_query(value):
    try:
        return datetime.strptime(value, '%Y-%m-%d').date()
    except (TypeError, ValueError):
        return timezone.localdate()


def _month_from_query(value):
    try:
        return datetime.strptime(value, '%Y-%m').date().replace(day=1)
    except (TypeError, ValueError):
        return timezone.localdate().replace(day=1)


def _transaction_totals(transactions):
    income_total = sum(
        (item.amount for item in transactions if item.kind == CashTransaction.Kind.INCOME),
        Decimal('0.00'),
    )
    expense_total = sum(
        (item.amount for item in transactions if item.kind == CashTransaction.Kind.EXPENSE),
        Decimal('0.00'),
    )
    return income_total, expense_total, income_total - expense_total


def _format_currency(value):
    formatted = f'{value:,.2f}'
    return f'R$ {formatted.replace(",", "_").replace(".", ",").replace("_", ".")}'


def _sync_expense_transaction(expense, user):
    cash_transaction = expense.cash_transaction or CashTransaction()
    cash_transaction.transaction_date = expense.expense_date
    cash_transaction.kind = CashTransaction.Kind.EXPENSE
    cash_transaction.description = (
        f'Gasto · {expense.get_category_display()}: {expense.description}'
    )[:180]
    cash_transaction.amount = expense.amount
    cash_transaction.payment_method = expense.payment_method
    supplier_note = f'Fornecedor: {expense.supplier.name}' if expense.supplier else ''
    cash_transaction.notes = '\n'.join(
        item for item in (supplier_note, expense.notes) if item
    )
    if cash_transaction.created_by_id is None:
        cash_transaction.created_by = user
    cash_transaction.save()
    if expense.cash_transaction_id != cash_transaction.pk:
        expense.cash_transaction = cash_transaction
        expense.save(update_fields=('cash_transaction',))


def _sync_payroll_transaction(payroll, user):
    cash_transaction = payroll.cash_transaction or CashTransaction()
    cash_transaction.transaction_date = payroll.payment_date
    cash_transaction.kind = CashTransaction.Kind.EXPENSE
    cash_transaction.description = (
        f'Folha de pagamento · {payroll.employee_name} · {payroll.competence:%m/%Y}'
    )[:180]
    cash_transaction.amount = payroll.net_salary
    cash_transaction.payment_method = payroll.payment_method
    cash_transaction.notes = payroll.notes
    if cash_transaction.created_by_id is None:
        cash_transaction.created_by = user
    cash_transaction.save()
    if payroll.cash_transaction_id != cash_transaction.pk:
        payroll.cash_transaction = cash_transaction
        payroll.save(update_fields=('cash_transaction',))


def _quote_queryset():
    return QuoteRequest.objects.select_related('customer__user', 'status_updated_by').prefetch_related(
        'products__category',
        'services',
    )


@staff_required
def dashboard_home(request):
    quotes = _quote_queryset()[:8]
    context = {
        'quotes': quotes,
        'pending_count': QuoteRequest.objects.filter(status=QuoteRequest.Status.PENDING).count(),
        'completed_count': QuoteRequest.objects.filter(status=QuoteRequest.Status.COMPLETED).count(),
        'cancelled_count': QuoteRequest.objects.filter(status=QuoteRequest.Status.CANCELLED).count(),
        'customer_count': Profile.objects.count(),
    }
    return render(request, 'dashboard/home.html', context)


@superuser_required
def administrator_list(request):
    administrators = User.objects.filter(is_staff=True).order_by('-is_superuser', 'first_name', 'username')
    return render(
        request,
        'dashboard/administrator_list.html',
        {'administrators': administrators},
    )


@superuser_required
def administrator_create(request):
    form = AdministratorCreationForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        administrator = form.save()
        messages.success(
            request,
            f'Administrador “{administrator.get_full_name() or administrator.username}” criado com sucesso.',
        )
        return redirect('dashboard:administrator_list')
    return render(request, 'dashboard/administrator_form.html', {'form': form})


@superuser_required
def administrator_edit(request, pk):
    administrator = get_object_or_404(User, pk=pk, is_staff=True)
    form = AdministratorUpdateForm(request.POST or None, instance=administrator)
    if request.method == 'POST' and form.is_valid():
        if administrator == request.user and not form.cleaned_data['is_active']:
            form.add_error('is_active', 'Você não pode desativar a conta que está usando.')
        else:
            administrator = form.save()
            messages.success(
                request,
                f'Dados de “{administrator.get_full_name() or administrator.username}” atualizados com sucesso.',
            )
            return redirect('dashboard:administrator_list')
    return render(
        request,
        'dashboard/administrator_form.html',
        {'form': form, 'administrator': administrator},
    )


@staff_required
def quote_list(request):
    selected_status = request.GET.get('status', '')
    quotes = _quote_queryset()
    if selected_status in QuoteRequest.Status.values:
        quotes = quotes.filter(status=selected_status)
    page_obj = Paginator(quotes, 12).get_page(request.GET.get('page'))
    return render(
        request,
        'dashboard/quote_list.html',
        {
            'quotes': page_obj,
            'page_obj': page_obj,
            'selected_status': selected_status,
            'status_choices': QuoteRequest.Status.choices,
        },
    )


@staff_required
def quote_detail(request, pk):
    quote = get_object_or_404(
        _quote_queryset().prefetch_related('status_history__admin'),
        pk=pk,
    )
    return render(request, 'dashboard/quote_detail.html', {'quote': quote})


@require_POST
@staff_required
def update_quote_status(request, pk):
    selected_status = request.POST.get('status')
    if selected_status not in QuoteRequest.Status.values:
        messages.error(request, 'Selecione um status válido.')
        return redirect('dashboard:quote_detail', pk=pk)

    with transaction.atomic():
        quote = get_object_or_404(QuoteRequest.objects.select_for_update(), pk=pk)
        changed_at = timezone.now()
        quote.status = selected_status
        quote.status_updated_by = request.user
        quote.status_updated_at = changed_at
        quote.save(update_fields=('status', 'status_updated_by', 'status_updated_at'))
        QuoteStatusHistory.objects.create(
            quote=quote,
            status=selected_status,
            admin=request.user,
        )

    messages.success(
        request,
        f'Orçamento #{quote.pk} marcado como {quote.get_status_display().lower()}.',
    )
    return redirect('dashboard:quote_detail', pk=quote.pk)


@require_POST
@staff_required
def next_quote_notification(request):
    quote = (
        _quote_queryset()
        .exclude(admin_notifications__admin=request.user)
        .order_by('requested_at', 'id')
        .first()
    )
    if quote is None:
        return JsonResponse({'quote': None})

    notification, created = QuoteAdminNotification.objects.get_or_create(
        quote=quote,
        admin=request.user,
    )
    if not created:
        return JsonResponse({'quote': None})

    return JsonResponse(
        {
            'quote': {
                'id': quote.pk,
                'customer': quote.customer_name,
                'requested_at': date_format(timezone.localtime(quote.requested_at), 'd/m/Y \\à\\s H:i'),
                'url': reverse('dashboard:quote_detail', kwargs={'pk': quote.pk}),
            },
        }
    )


@staff_required
def customer_list(request):
    query = request.GET.get('q', '').strip()
    customers = Profile.objects.select_related('user').annotate(
        quote_count=Count('quote_requests'),
    ).order_by('-user__date_joined')
    if query:
        customer_query = (
            Q(full_name_hash=blind_index(normalize_text(query), 'profile.full_name'))
            | Q(corporate_name_hash=blind_index(normalize_text(query), 'profile.corporate_name'))
            | Q(email_hash=blind_index(query.strip().lower(), 'profile.email'))
        )
        digits = only_digits(query)
        if digits:
            customer_query |= Q(document_hash=blind_index(digits, 'profile.document'))
            customer_query |= Q(phone_hash=blind_index(digits, 'profile.phone'))
        customers = customers.filter(customer_query)
    page_obj = Paginator(customers, 15).get_page(request.GET.get('page'))
    return render(
        request,
        'dashboard/customer_list.html',
        {'customers': page_obj, 'page_obj': page_obj, 'query': query},
    )


@staff_required
def customer_edit(request, pk):
    customer = get_object_or_404(Profile.objects.select_related('user'), pk=pk)
    form = CustomerManagementForm(
        request.POST or None,
        request.FILES or None,
        instance=customer,
    )
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, f'Dados de {customer} atualizados com sucesso.')
        return redirect('dashboard:customer_list')
    return render(
        request,
        'dashboard/customer_form.html',
        {'form': form, 'customer': customer},
    )


@staff_required
def product_list(request):
    products = Product.objects.select_related('category').all()
    category_form = CategoryManagementForm(request.POST or None)
    if request.method == 'POST' and category_form.is_valid():
        category = category_form.save()
        messages.success(request, f'Categoria “{category.name}” cadastrada com sucesso.')
        return redirect('dashboard:product_list')
    categories = Category.objects.annotate(product_count=Count('products')).all()
    return render(
        request,
        'dashboard/product_list.html',
        {
            'products': products,
            'categories': categories,
            'category_form': category_form,
        },
    )


@staff_required
def product_form(request, pk=None):
    product = get_object_or_404(Product, pk=pk) if pk is not None else None
    form = ProductManagementForm(
        request.POST or None,
        request.FILES or None,
        instance=product,
    )
    if request.method == 'POST' and form.is_valid():
        product = form.save()
        messages.success(request, f'Produto “{product.name}” salvo com sucesso.')
        if 'save_and_add_another' in request.POST:
            return redirect('dashboard:product_create')
        return redirect('dashboard:product_list')
    return render(
        request,
        'dashboard/product_form.html',
        {'form': form, 'product': product},
    )


@require_POST
@staff_required
def product_delete(request, pk):
    product = get_object_or_404(Product, pk=pk)
    product_name = product.name
    product.delete()
    messages.success(request, f'Produto “{product_name}” excluído com sucesso.')
    return redirect('dashboard:product_list')


@staff_required
def product_stock_exit(request):
    initial = {}
    if request.method == 'GET':
        selected_product = Product.objects.filter(pk=request.GET.get('product')).first()
        if selected_product is not None:
            initial['product'] = selected_product

    form = ProductStockExitForm(request.POST or None, initial=initial)
    if request.method == 'POST' and form.is_valid():
        selected_product = form.cleaned_data['product']
        quantity = form.cleaned_data['quantity']
        notes = form.cleaned_data['notes']
        stock_exit_created = False

        with transaction.atomic():
            try:
                product = Product.objects.select_for_update().get(pk=selected_product.pk)
            except Product.DoesNotExist:
                form.add_error('product', 'Este produto não está mais disponível.')
            else:
                if quantity > product.stock_quantity:
                    form.add_error(
                        'quantity',
                        f'Estoque insuficiente. Há {product.stock_quantity} unidade(s) disponível(is).',
                    )
                else:
                    stock_before = product.stock_quantity
                    product.stock_quantity -= quantity
                    product.save(update_fields=('stock_quantity',))
                    ProductStockExit.objects.create(
                        product=product,
                        product_name=product.name,
                        quantity=quantity,
                        stock_before=stock_before,
                        stock_after=product.stock_quantity,
                        notes=notes,
                        created_by=request.user,
                    )
                    stock_exit_created = True

        if stock_exit_created:
            messages.success(
                request,
                f'Saída de {quantity} unidade(s) de “{product.name}” registrada. '
                f'Estoque atual: {product.stock_quantity}.',
            )
            return redirect('dashboard:product_stock_exit')

    products = Product.objects.select_related('category').all()
    total_stock = products.aggregate(total=Sum('stock_quantity'))['total'] or 0
    stock_exits = ProductStockExit.objects.select_related('product', 'created_by')[:100]
    return render(
        request,
        'dashboard/product_stock_exit.html',
        {
            'form': form,
            'products': products,
            'total_stock': total_stock,
            'stock_exits': stock_exits,
        },
    )


@staff_required
def service_list(request):
    return render(
        request,
        'dashboard/service_list.html',
        {'services': Service.objects.all()},
    )


@staff_required
def service_form(request, pk=None):
    service = get_object_or_404(Service, pk=pk) if pk is not None else None
    form = ServiceManagementForm(
        request.POST or None,
        request.FILES or None,
        instance=service,
    )
    if request.method == 'POST' and form.is_valid():
        service = form.save()
        messages.success(request, f'Serviço “{service.name}” salvo com sucesso.')
        if 'save_and_add_another' in request.POST:
            return redirect('dashboard:service_create')
        return redirect('dashboard:service_list')
    return render(
        request,
        'dashboard/service_form.html',
        {'form': form, 'service': service},
    )


@require_POST
@staff_required
def service_delete(request, pk):
    service = get_object_or_404(Service, pk=pk)
    service_name = service.name
    service.delete()
    messages.success(request, f'Serviço “{service_name}” excluído com sucesso.')
    return redirect('dashboard:service_list')


@staff_required
def cash_daily(request):
    selected_date = _date_from_query(request.GET.get('date'))
    transactions = list(
        CashTransaction.objects.select_related('created_by').filter(transaction_date=selected_date)
    )
    income_total, expense_total, balance = _transaction_totals(transactions)
    return render(
        request,
        'dashboard/cash_daily.html',
        {
            'transactions': transactions,
            'selected_date': selected_date,
            'income_total': income_total,
            'expense_total': expense_total,
            'balance': balance,
        },
    )


@staff_required
def cash_transaction_form(request, pk=None):
    cash_transaction = get_object_or_404(CashTransaction, pk=pk) if pk is not None else None
    if cash_transaction is not None and (
        hasattr(cash_transaction, 'managed_expense')
        or hasattr(cash_transaction, 'payroll')
        or hasattr(cash_transaction, 'sale_payment')
        or hasattr(cash_transaction, 'sale_reversal')
    ):
        messages.info(
            request,
            'Este lançamento é sincronizado. Faça a alteração na tela que o originou.',
        )
        if hasattr(cash_transaction, 'managed_expense'):
            return redirect('dashboard:expense_edit', pk=cash_transaction.managed_expense.pk)
        if hasattr(cash_transaction, 'sale_payment'):
            return redirect('sales:detail', pk=cash_transaction.sale_payment.pk)
        if hasattr(cash_transaction, 'sale_reversal'):
            return redirect('sales:detail', pk=cash_transaction.sale_reversal.pk)
        return redirect('dashboard:payroll_edit', pk=cash_transaction.payroll.pk)
    initial = {}
    if cash_transaction is None and request.method == 'GET':
        initial['transaction_date'] = _date_from_query(request.GET.get('date'))
    form = CashTransactionForm(
        request.POST or None,
        instance=cash_transaction,
        initial=initial,
    )
    if request.method == 'POST' and form.is_valid():
        cash_transaction = form.save(commit=False)
        if cash_transaction.created_by_id is None:
            cash_transaction.created_by = request.user
        cash_transaction.save()
        messages.success(request, f'Lançamento “{cash_transaction.description}” salvo com sucesso.')
        if 'save_and_add_another' in request.POST:
            create_url = reverse('dashboard:cash_transaction_create')
            return redirect(f'{create_url}?date={cash_transaction.transaction_date:%Y-%m-%d}')
        daily_url = reverse('dashboard:cash_daily')
        return redirect(f'{daily_url}?date={cash_transaction.transaction_date:%Y-%m-%d}')
    return render(
        request,
        'dashboard/cash_transaction_form.html',
        {'form': form, 'cash_transaction': cash_transaction},
    )


@require_POST
@staff_required
def cash_transaction_delete(request, pk):
    cash_transaction = get_object_or_404(CashTransaction, pk=pk)
    if (
        hasattr(cash_transaction, 'managed_expense')
        or hasattr(cash_transaction, 'payroll')
        or hasattr(cash_transaction, 'sale_payment')
        or hasattr(cash_transaction, 'sale_reversal')
    ):
        messages.error(
            request,
            'Este lançamento é auditável e deve ser tratado pela operação que o originou.',
        )
        daily_url = reverse('dashboard:cash_daily')
        return redirect(f'{daily_url}?date={cash_transaction.transaction_date:%Y-%m-%d}')
    selected_date = cash_transaction.transaction_date
    description = cash_transaction.description
    cash_transaction.delete()
    messages.success(request, f'Lançamento “{description}” excluído com sucesso.')
    daily_url = reverse('dashboard:cash_daily')
    return redirect(f'{daily_url}?date={selected_date:%Y-%m-%d}')


@staff_required
def monthly_finance(request):
    selected_month = _month_from_query(request.GET.get('month'))
    transactions = list(
        CashTransaction.objects.select_related('created_by').filter(
            transaction_date__year=selected_month.year,
            transaction_date__month=selected_month.month,
        )
    )
    income_total, expense_total, balance = _transaction_totals(transactions)
    return render(
        request,
        'dashboard/monthly_finance.html',
        {
            'transactions': transactions,
            'selected_month': selected_month,
            'selected_month_value': selected_month.strftime('%Y-%m'),
            'income_total': income_total,
            'expense_total': expense_total,
            'balance': balance,
        },
    )


@staff_required
def monthly_finance_pdf(request):
    selected_month = _month_from_query(request.GET.get('month'))
    transactions = list(
        CashTransaction.objects.filter(
            transaction_date__year=selected_month.year,
            transaction_date__month=selected_month.month,
        ).order_by('transaction_date', 'created_at', 'id')
    )
    income_total, expense_total, balance = _transaction_totals(transactions)
    month_label = date_format(selected_month, 'F \\d\\e Y').capitalize()
    lines = [
        f'Competência: {month_label}',
        f'Emitido em: {timezone.localtime():%d/%m/%Y às %H:%M}',
        '',
        f'Total de entradas: {_format_currency(income_total)}',
        f'Total de saídas: {_format_currency(expense_total)}',
        f'Resultado do mês: {_format_currency(balance)}',
        '',
        'Lançamentos',
        '-' * 88,
    ]
    if transactions:
        for item in transactions:
            signed_amount = item.amount if item.kind == CashTransaction.Kind.INCOME else -item.amount
            lines.append(
                f'{item.transaction_date:%d/%m/%Y} | {item.get_kind_display():7} | '
                f'{item.get_payment_method_display():18} | {_format_currency(signed_amount):>16} | '
                f'{item.description}'
            )
            if item.notes:
                lines.append(f'  Observações: {item.notes}')
    else:
        lines.append('Nenhum lançamento cadastrado nesta competência.')

    pdf = build_text_pdf('Relatório mensal - Globo Vidraçaria', lines)
    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = (
        f'attachment; filename="faturamento-{selected_month:%Y-%m}.pdf"'
    )
    return response


@staff_required
def profit_calculator(request):
    return render(request, 'dashboard/profit_calculator.html')


@staff_required
def expense_list(request):
    selected_month = _month_from_query(request.GET.get('month'))
    selected_category = request.GET.get('category', '').strip()
    expenses = Expense.objects.select_related('supplier', 'created_by').filter(
        expense_date__year=selected_month.year,
        expense_date__month=selected_month.month,
    )
    if selected_category in Expense.Category.values:
        expenses = expenses.filter(category=selected_category)
    else:
        selected_category = ''
    expense_total = expenses.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    return render(
        request,
        'dashboard/expense_list.html',
        {
            'expenses': expenses,
            'selected_month': selected_month,
            'selected_month_value': selected_month.strftime('%Y-%m'),
            'selected_category': selected_category,
            'categories': Expense.Category.choices,
            'expense_total': expense_total,
        },
    )


@staff_required
def expense_form(request, pk=None):
    expense = get_object_or_404(Expense, pk=pk) if pk is not None else None
    initial = {}
    if expense is None and request.method == 'GET':
        initial['expense_date'] = _date_from_query(request.GET.get('date'))
    form = ExpenseForm(request.POST or None, instance=expense, initial=initial)
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            expense = form.save(commit=False)
            if expense.created_by_id is None:
                expense.created_by = request.user
            expense.save()
            _sync_expense_transaction(expense, request.user)
        messages.success(
            request,
            f'Gasto “{expense.description}” salvo e incluído nas saídas do faturamento.',
        )
        return redirect(
            f'{reverse("dashboard:expense_list")}?month={expense.expense_date:%Y-%m}'
        )
    return render(
        request,
        'dashboard/expense_form.html',
        {'form': form, 'expense': expense},
    )


@require_POST
@staff_required
def expense_delete(request, pk):
    expense = get_object_or_404(Expense, pk=pk)
    selected_month = expense.expense_date.strftime('%Y-%m')
    description = expense.description
    with transaction.atomic():
        cash_transaction = expense.cash_transaction
        expense.delete()
        if cash_transaction is not None:
            cash_transaction.delete()
    messages.success(request, f'Gasto “{description}” excluído do controle financeiro.')
    return redirect(f'{reverse("dashboard:expense_list")}?month={selected_month}')


@staff_required
def employee_list(request):
    return render(
        request,
        'dashboard/employee_list.html',
        {'employees': Employee.objects.all()},
    )


@staff_required
def employee_form(request, pk=None):
    employee = get_object_or_404(Employee, pk=pk) if pk is not None else None
    form = EmployeeForm(
        request.POST or None,
        request.FILES or None,
        instance=employee,
    )
    if request.method == 'POST' and form.is_valid():
        employee = form.save()
        messages.success(request, f'Funcionário “{employee.full_name}” salvo com sucesso.')
        if 'save_and_add_another' in request.POST:
            return redirect('dashboard:employee_create')
        return redirect('dashboard:employee_list')
    return render(
        request,
        'dashboard/employee_form.html',
        {'form': form, 'employee': employee},
    )


@require_POST
@staff_required
def employee_delete(request, pk):
    employee = get_object_or_404(Employee, pk=pk)
    employee_name = employee.full_name
    try:
        employee.delete()
    except ProtectedError:
        messages.error(
            request,
            'Este funcionário possui folhas de pagamento e não pode ser excluído. '
            'Você ainda pode editar o cadastro.',
        )
        return redirect('dashboard:employee_list')
    messages.success(request, f'Funcionário “{employee_name}” excluído com sucesso.')
    return redirect('dashboard:employee_list')


@staff_required
def payroll_list(request):
    selected_month = _month_from_query(request.GET.get('month'))
    payrolls = list(
        Payroll.objects.select_related('employee', 'created_by').filter(
            competence=selected_month
        )
    )
    employees = list(Employee.objects.all())
    payroll_by_employee = {payroll.employee_id: payroll for payroll in payrolls}
    employee_rows = [
        {'employee': employee, 'payroll': payroll_by_employee.get(employee.pk)}
        for employee in employees
    ]
    net_total = sum((payroll.net_salary for payroll in payrolls), Decimal('0.00'))
    return render(
        request,
        'dashboard/payroll_list.html',
        {
            'payrolls': payrolls,
            'employee_rows': employee_rows,
            'selected_month': selected_month,
            'selected_month_value': selected_month.strftime('%Y-%m'),
            'net_total': net_total,
        },
    )


@staff_required
def payroll_form(request, pk=None):
    payroll = get_object_or_404(Payroll, pk=pk) if pk is not None else None
    initial = {}
    if payroll is None and request.method == 'GET':
        competence = _month_from_query(request.GET.get('month'))
        initial['competence'] = competence
        initial['payment_date'] = date(
            competence.year,
            competence.month,
            monthrange(competence.year, competence.month)[1],
        )
        employee = Employee.objects.filter(pk=request.GET.get('employee')).first()
        if employee is not None:
            initial['employee'] = employee
            initial['gross_salary'] = employee.monthly_salary
    form = PayrollForm(request.POST or None, instance=payroll, initial=initial)
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            payroll = form.save(commit=False)
            if payroll.created_by_id is None:
                payroll.created_by = request.user
            payroll.save()
            _sync_payroll_transaction(payroll, request.user)
        messages.success(
            request,
            f'Folha de {payroll.employee_name} salva e incluída nas saídas do faturamento.',
        )
        return redirect(
            f'{reverse("dashboard:payroll_list")}?month={payroll.competence:%Y-%m}'
        )
    return render(
        request,
        'dashboard/payroll_form.html',
        {'form': form, 'payroll': payroll},
    )


@require_POST
@staff_required
def payroll_quick_create(request, employee_pk):
    employee = get_object_or_404(Employee, pk=employee_pk)
    selected_month = _month_from_query(request.POST.get('month'))
    if employee.monthly_salary <= 0:
        messages.error(request, 'Cadastre um salário maior que zero antes de gerar a folha.')
        return redirect(f'{reverse("dashboard:payroll_list")}?month={selected_month:%Y-%m}')

    existing = Payroll.objects.filter(employee=employee, competence=selected_month).first()
    if existing is not None:
        messages.info(request, 'A folha deste funcionário já existe para a competência selecionada.')
        return redirect(f'{reverse("dashboard:payroll_list")}?month={selected_month:%Y-%m}')

    payment_date = date(
        selected_month.year,
        selected_month.month,
        monthrange(selected_month.year, selected_month.month)[1],
    )
    with transaction.atomic():
        payroll = Payroll.objects.create(
            employee=employee,
            competence=selected_month,
            gross_salary=employee.monthly_salary,
            payment_date=payment_date,
            payment_method=CashTransaction.PaymentMethod.PIX,
            created_by=request.user,
        )
        _sync_payroll_transaction(payroll, request.user)
    messages.success(
        request,
        f'Folha de {employee.full_name} gerada. O PDF já está pronto para impressão.',
    )
    return redirect(f'{reverse("dashboard:payroll_list")}?month={selected_month:%Y-%m}')


@staff_required
def payroll_pdf(request, pk):
    payroll = get_object_or_404(Payroll.objects.select_related('employee'), pk=pk)
    settings_record = SystemSettings.objects.first() or SystemSettings()
    company_document = only_digits(settings_record.tax_id)
    if len(company_document) == 14:
        company_document = (
            f'{company_document[:2]}.{company_document[2:5]}.{company_document[5:8]}/'
            f'{company_document[8:12]}-{company_document[12:]}'
        )
    competence_label = date_format(payroll.competence, 'F \d\e Y').capitalize()
    lines = [
        settings_record.company_name,
        *([f'CNPJ: {company_document}'] if company_document else []),
        *([f'Endereço: {settings_record.address}'] if settings_record.address else []),
        '',
        f'RECIBO DE PAGAMENTO — {competence_label}',
        '-' * 88,
        f'Funcionário: {payroll.employee_name}',
        f'CPF: {payroll.formatted_employee_cpf}',
        f'Data do pagamento: {payroll.payment_date:%d/%m/%Y}',
        f'Forma de pagamento: {payroll.get_payment_method_display()}',
        '',
        f'Salário-base: {_format_currency(payroll.gross_salary)}',
        f'Acréscimos: {_format_currency(payroll.additions)}',
        f'Descontos: {_format_currency(payroll.deductions)}',
        '-' * 48,
        f'VALOR LÍQUIDO: {_format_currency(payroll.net_salary)}',
        '',
    ]
    if payroll.notes:
        lines.extend((f'Observações: {payroll.notes}', ''))
    lines.extend(
        (
            'Declaro ter recebido o valor líquido discriminado neste recibo.',
            '',
            '',
            '____________________________________    ____________________________________',
            f'{payroll.employee_name:<38}    '
            f'{settings_record.financial_manager or "Responsável financeiro"}',
            'Assinatura do funcionário                 Assinatura do responsável financeiro',
        )
    )
    pdf = build_text_pdf('Folha de pagamento - Globo Vidraçaria', lines)
    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = (
        f'inline; filename="folha-{payroll.employee_id}-{payroll.competence:%Y-%m}.pdf"'
    )
    return response


@require_POST
@staff_required
def payroll_delete(request, pk):
    payroll = get_object_or_404(Payroll, pk=pk)
    selected_month = payroll.competence.strftime('%Y-%m')
    employee_name = payroll.employee_name
    with transaction.atomic():
        cash_transaction = payroll.cash_transaction
        payroll.delete()
        if cash_transaction is not None:
            cash_transaction.delete()
    messages.success(request, f'Folha de {employee_name} excluída do controle financeiro.')
    return redirect(f'{reverse("dashboard:payroll_list")}?month={selected_month}')


@staff_required
def supplier_list(request):
    query = request.GET.get('q', '').strip()
    suppliers = Supplier.objects.annotate(expense_count=Count('expenses'))
    if query:
        supplier_query = (
            Q(name_hash=blind_index(normalize_text(query), 'supplier.name'))
            | Q(contact_name_hash=blind_index(normalize_text(query), 'supplier.contact_name'))
            | Q(email_hash=blind_index(query.strip().lower(), 'supplier.email'))
        )
        digits = only_digits(query)
        if digits:
            supplier_query |= Q(tax_id_hash=blind_index(digits, 'supplier.tax_id'))
            supplier_query |= Q(phone_hash=blind_index(digits, 'supplier.phone'))
        suppliers = suppliers.filter(supplier_query)
    return render(
        request,
        'dashboard/supplier_list.html',
        {'suppliers': suppliers, 'query': query},
    )


@staff_required
def supplier_form(request, pk=None):
    supplier = get_object_or_404(Supplier, pk=pk) if pk is not None else None
    form = SupplierForm(request.POST or None, instance=supplier)
    if request.method == 'POST' and form.is_valid():
        supplier = form.save()
        messages.success(request, f'Fornecedor “{supplier.name}” salvo com sucesso.')
        return redirect('dashboard:supplier_list')
    return render(
        request,
        'dashboard/supplier_form.html',
        {'form': form, 'supplier': supplier},
    )


@require_POST
@staff_required
def supplier_delete(request, pk):
    supplier = get_object_or_404(Supplier, pk=pk)
    supplier_name = supplier.name
    supplier.delete()
    messages.success(request, f'Fornecedor “{supplier_name}” excluído com sucesso.')
    return redirect('dashboard:supplier_list')


@staff_required
def system_settings(request):
    settings_record = SystemSettings.objects.first() or SystemSettings(pk=1)
    form = SystemSettingsForm(request.POST or None, instance=settings_record)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Configurações do sistema salvas com sucesso.')
        return redirect('dashboard:system_settings')
    return render(
        request,
        'dashboard/system_settings.html',
        {'form': form, 'settings_record': settings_record},
    )


@login_required
def request_quote(request):
    if request.user.is_staff:
        return redirect('dashboard:home')

    customer = Profile.objects.filter(user=request.user).first()
    if customer is None:
        messages.error(request, 'Não encontramos os dados do seu perfil.')
        return redirect('accounts:login')

    if not customer.has_complete_address:
        messages.warning(
            request,
            'Complete seu endereço antes de solicitar um orçamento.',
        )
        return redirect(f'{reverse("accounts:edit_profile")}?next=quote')

    form = QuoteRequestForm(request.POST or None)
    next_allowed_at = QuoteRequest.next_allowed_at_for(customer)
    now = timezone.now()
    can_request = next_allowed_at is None or now >= next_allowed_at

    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            locked_customer = Profile.objects.select_for_update().get(pk=customer.pk)
            if not locked_customer.has_complete_address:
                messages.warning(request, 'Complete seu endereço antes de solicitar um orçamento.')
                return redirect(f'{reverse("accounts:edit_profile")}?next=quote')

            next_allowed_at = QuoteRequest.next_allowed_at_for(locked_customer)
            now = timezone.now()
            if next_allowed_at is not None and now < next_allowed_at:
                messages.warning(
                    request,
                    'Você já enviou uma solicitação. Aguarde o contador terminar para enviar outra.',
                )
                return redirect('dashboard:request_quote')

            quote = form.save(commit=False)
            quote.copy_customer_data(locked_customer)
            quote.save()
            form.instance = quote
            form.save_m2m()

        messages.success(
            request,
            f'Solicitação #{quote.pk} enviada! Nossa equipe já recebeu o seu pedido.',
        )
        return redirect('dashboard:request_quote')

    recent_quotes = _quote_queryset().filter(customer=customer)[:5]
    return render(
        request,
        'dashboard/request_quote.html',
        {
            'form': form,
            'customer': customer,
            'can_request': can_request,
            'next_allowed_at': next_allowed_at,
            'recent_quotes': recent_quotes,
        },
    )
