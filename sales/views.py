from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from dashboard.decorators import staff_required
from accounts.models import normalize_text, only_digits
from app.crypto import blind_index

from .forms import (
    CancellationForm,
    MaterialItemForm,
    ProductItemForm,
    SaleForm,
    ServiceItemForm,
)
from .models import Sale, SaleItem
from .services import cancel_sale, complete_sale


def _sale_queryset():
    return Sale.objects.select_related(
        'employee', 'customer', 'cancelled_by', 'cash_transaction',
        'reversal_cash_transaction',
    ).prefetch_related('items', 'stock_movements')


def _error_text(error):
    if hasattr(error, 'message_dict'):
        return ' '.join(message for messages_list in error.message_dict.values() for message in messages_list)
    return ' '.join(error.messages)


@staff_required
def sale_list(request):
    sales = _sale_queryset()
    selected_status = request.GET.get('status', '').strip()
    selected_customer_type = request.GET.get('customer_type', '').strip()
    selected_payment = request.GET.get('payment_method', '').strip()
    search = request.GET.get('q', '').strip()
    if selected_status in Sale.Status.values:
        sales = sales.filter(status=selected_status)
    else:
        selected_status = ''
    if selected_customer_type in Sale.CustomerType.values:
        sales = sales.filter(customer_type=selected_customer_type)
    else:
        selected_customer_type = ''
    if selected_payment in dict(Sale._meta.get_field('payment_method').choices):
        sales = sales.filter(payment_method=selected_payment)
    else:
        selected_payment = ''
    if search:
        number_search = search.upper().removeprefix('VEN-')
        query = Q(
            customer_name_hash=blind_index(normalize_text(search), 'sale.customer_name')
        )
        digits = only_digits(search)
        if digits:
            query |= Q(
                customer_document_hash=blind_index(digits, 'sale.customer_document')
            )
        if number_search.isdigit():
            query |= Q(pk=int(number_search))
        sales = sales.filter(query)
    page_obj = Paginator(sales, 20).get_page(request.GET.get('page'))
    return render(request, 'sales/sale_list.html', {
        'page_obj': page_obj,
        'sales': page_obj.object_list,
        'selected_status': selected_status,
        'selected_customer_type': selected_customer_type,
        'selected_payment': selected_payment,
        'search': search,
        'status_choices': Sale.Status.choices,
        'customer_type_choices': Sale.CustomerType.choices,
        'payment_choices': Sale._meta.get_field('payment_method').choices,
    })


@staff_required
def sale_create(request):
    form = SaleForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        sale = form.save(employee=request.user)
        messages.success(request, f'{sale.number} criada como rascunho. Inclua os itens da venda.')
        return redirect('sales:edit', pk=sale.pk)
    return render(request, 'sales/sale_create.html', {'form': form})


@staff_required
def sale_edit(request, pk):
    sale = get_object_or_404(_sale_queryset(), pk=pk)
    if not sale.can_edit:
        messages.info(request, 'Vendas concluídas ou canceladas são somente para consulta.')
        return redirect('sales:detail', pk=sale.pk)

    sale_form = SaleForm(instance=sale)
    product_form = ProductItemForm(prefix='product')
    material_form = MaterialItemForm(prefix='material')
    service_form = ServiceItemForm(prefix='service')
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'save_sale':
            sale_form = SaleForm(request.POST, instance=sale)
            if sale_form.is_valid():
                sale_form.save(employee=request.user)
                messages.success(request, 'Dados e pagamento do rascunho atualizados.')
                return redirect('sales:edit', pk=sale.pk)
        elif action == 'add_product':
            product_form = ProductItemForm(request.POST, prefix='product')
            if product_form.is_valid():
                product_form.save(sale)
                sale.recalculate_totals(save=True)
                messages.success(request, 'Produto incluído na venda.')
                return redirect('sales:edit', pk=sale.pk)
        elif action == 'add_material':
            material_form = MaterialItemForm(request.POST, prefix='material')
            if material_form.is_valid():
                material_form.save(sale)
                sale.recalculate_totals(save=True)
                messages.success(request, 'Material por m² incluído na venda.')
                return redirect('sales:edit', pk=sale.pk)
        elif action == 'add_service':
            service_form = ServiceItemForm(request.POST, prefix='service')
            if service_form.is_valid():
                service_form.save(sale)
                sale.recalculate_totals(save=True)
                messages.success(request, 'Serviço incluído na venda.')
                return redirect('sales:edit', pk=sale.pk)
    sale.refresh_from_db()
    return render(request, 'sales/sale_edit.html', {
        'sale': sale,
        'sale_form': sale_form,
        'product_form': product_form,
        'material_form': material_form,
        'service_form': service_form,
    })


@require_POST
@staff_required
def sale_item_remove(request, pk, item_pk):
    sale = get_object_or_404(Sale, pk=pk)
    if not sale.can_edit:
        messages.error(request, 'Os itens desta venda não podem mais ser alterados.')
        return redirect('sales:detail', pk=sale.pk)
    item = get_object_or_404(SaleItem, pk=item_pk, sale=sale)
    remaining_subtotal = sum(
        (other.total for other in sale.items.exclude(pk=item.pk)),
        Sale._meta.get_field('subtotal').default,
    )
    if sale.discount > remaining_subtotal:
        messages.error(
            request,
            'Reduza o desconto geral antes de remover este item.',
        )
        return redirect('sales:edit', pk=sale.pk)
    description = item.description
    item.delete()
    sale.recalculate_totals(save=True)
    messages.success(request, f'“{description}” removido da venda.')
    return redirect('sales:edit', pk=sale.pk)


@staff_required
def sale_review(request, pk):
    sale = get_object_or_404(_sale_queryset(), pk=pk)
    if not sale.can_edit:
        return redirect('sales:detail', pk=sale.pk)
    try:
        sale.recalculate_totals(save=True)
    except ValidationError as error:
        messages.error(request, _error_text(error))
        return redirect('sales:edit', pk=sale.pk)
    return render(request, 'sales/sale_review.html', {'sale': sale})


@require_POST
@staff_required
def sale_complete(request, pk):
    try:
        sale = complete_sale(pk, request.user)
    except ValidationError as error:
        messages.error(request, _error_text(error))
        return redirect('sales:review', pk=pk)
    messages.success(request, f'{sale.number} concluída. Caixa e estoque foram registrados.')
    return redirect('sales:detail', pk=sale.pk)


@staff_required
def sale_detail(request, pk):
    sale = get_object_or_404(_sale_queryset(), pk=pk)
    return render(request, 'sales/sale_detail.html', {'sale': sale})


@staff_required
def sale_cancel(request, pk):
    sale = get_object_or_404(_sale_queryset(), pk=pk)
    if sale.status == Sale.Status.CANCELLED:
        messages.info(request, 'Esta venda já está cancelada e não foi estornada novamente.')
        return redirect('sales:detail', pk=sale.pk)
    if sale.status != Sale.Status.COMPLETED:
        messages.error(request, 'Somente uma venda concluída pode ser cancelada.')
        return redirect('sales:detail', pk=sale.pk)
    form = CancellationForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        try:
            sale = cancel_sale(sale.pk, request.user, form.cleaned_data['reason'])
        except ValidationError as error:
            form.add_error(None, _error_text(error))
        else:
            messages.success(request, f'{sale.number} cancelada; estoque e caixa foram estornados.')
            return redirect('sales:detail', pk=sale.pk)
    return render(request, 'sales/sale_cancel.html', {'sale': sale, 'form': form})
