from collections import defaultdict
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from dashboard.models import CashTransaction
from products.models import Product, ProductStockExit

from .models import Sale, SaleItem, SaleStockMovement, money


def _locked_sale(sale_id):
    return (
        Sale.objects.select_for_update()
        .select_related('customer', 'employee')
        .get(pk=sale_id)
    )


def _product_quantities(items):
    quantities = defaultdict(int)
    for item in items:
        if item.item_type != SaleItem.ItemType.PRODUCT:
            continue
        if not item.product_id:
            raise ValidationError('Um produto desta venda não está mais disponível no cadastro.')
        if item.quantity != item.quantity.to_integral_value():
            raise ValidationError(f'A quantidade de “{item.description}” deve ser inteira.')
        quantities[item.product_id] += int(item.quantity)
    return quantities


@transaction.atomic
def complete_sale(sale_id, user):
    sale = _locked_sale(sale_id)
    if sale.status == Sale.Status.COMPLETED:
        return sale
    if sale.status == Sale.Status.CANCELLED:
        raise ValidationError('Uma venda cancelada não pode ser concluída novamente.')

    items = list(
        sale.items.select_related('product', 'material', 'service').order_by('id')
    )
    if not items:
        raise ValidationError('Inclua pelo menos um item antes de concluir a venda.')

    for item in items:
        # Recalcula e persiste cada snapshot no servidor antes de somar a venda.
        item.save()
    if sale.customer_type == Sale.CustomerType.REGISTERED:
        sale.copy_registered_customer()
    sale.full_clean()
    sale.recalculate_totals()
    if sale.total <= 0:
        raise ValidationError('O total da venda deve ser maior que zero.')
    if not sale.payment_method:
        raise ValidationError('Selecione a forma de pagamento antes de concluir.')
    if money(sale.amount_paid) != sale.total:
        raise ValidationError(
            f'O total pago deve corresponder ao total da venda ({sale.total:.2f}).'
        )

    requested = _product_quantities(items)
    locked_products = {
        product.pk: product
        for product in Product.objects.select_for_update().filter(pk__in=sorted(requested))
    }
    for product_id, quantity in requested.items():
        product = locked_products.get(product_id)
        if product is None:
            raise ValidationError('Um produto desta venda não está mais disponível no cadastro.')
        if product.stock_quantity < quantity:
            raise ValidationError(
                f'Estoque insuficiente para “{product.name}”: '
                f'{product.stock_quantity} disponível(is), {quantity} solicitado(s).'
            )

    cash_transaction = CashTransaction.objects.create(
        transaction_date=timezone.localdate(),
        kind=CashTransaction.Kind.INCOME,
        description=f'Venda {sale.number} · {sale.customer_name}'[:180],
        amount=sale.total,
        payment_method=sale.payment_method,
        notes=sale.notes,
        created_by=user,
    )

    for item in items:
        if item.item_type != SaleItem.ItemType.PRODUCT:
            continue
        product = locked_products[item.product_id]
        quantity = int(item.quantity)
        stock_before = product.stock_quantity
        product.stock_quantity = stock_before - quantity
        product.save(update_fields=('stock_quantity',))
        stock_exit = ProductStockExit.objects.create(
            product=product,
            product_name=item.description,
            quantity=quantity,
            stock_before=stock_before,
            stock_after=product.stock_quantity,
            notes=f'Baixa automática da venda {sale.number}',
            created_by=user,
        )
        SaleStockMovement.objects.create(
            sale=sale,
            sale_item=item,
            product=product,
            kind=SaleStockMovement.Kind.EXIT,
            quantity=quantity,
            stock_before=stock_before,
            stock_after=product.stock_quantity,
            product_stock_exit=stock_exit,
            created_by=user,
        )

    sale.status = Sale.Status.COMPLETED
    sale.payment_status = Sale.PaymentStatus.PAID
    sale.cash_transaction = cash_transaction
    sale.completed_at = timezone.now()
    sale.save(
        update_fields=(
            'status', 'customer_name', 'customer_document', 'customer_contact',
            'customer_email', 'customer_address', 'subtotal', 'discount', 'total',
            'amount_paid', 'payment_status', 'cash_transaction', 'completed_at', 'updated_at',
        )
    )
    return sale


@transaction.atomic
def cancel_sale(sale_id, user, reason):
    sale = _locked_sale(sale_id)
    if sale.status == Sale.Status.CANCELLED:
        return sale
    if sale.status != Sale.Status.COMPLETED:
        raise ValidationError('Somente uma venda concluída pode ser cancelada.')
    reason = (reason or '').strip()
    if not reason:
        raise ValidationError('Informe o motivo do cancelamento.')

    exits = list(
        sale.stock_movements.select_related('product', 'sale_item')
        .filter(kind=SaleStockMovement.Kind.EXIT)
        .order_by('id')
    )
    product_ids = sorted({movement.product_id for movement in exits})
    locked_products = {
        product.pk: product
        for product in Product.objects.select_for_update().filter(pk__in=product_ids)
    }
    if len(locked_products) != len(product_ids):
        raise ValidationError('Não foi possível localizar todos os produtos para devolver o estoque.')

    for movement in exits:
        if SaleStockMovement.objects.filter(
            sale_item=movement.sale_item,
            kind=SaleStockMovement.Kind.RETURN,
        ).exists():
            continue
        product = locked_products[movement.product_id]
        stock_before = product.stock_quantity
        product.stock_quantity = stock_before + movement.quantity
        product.save(update_fields=('stock_quantity',))
        SaleStockMovement.objects.create(
            sale=sale,
            sale_item=movement.sale_item,
            product=product,
            kind=SaleStockMovement.Kind.RETURN,
            quantity=movement.quantity,
            stock_before=stock_before,
            stock_after=product.stock_quantity,
            created_by=user,
        )

    reversal = CashTransaction.objects.create(
        transaction_date=timezone.localdate(),
        kind=CashTransaction.Kind.EXPENSE,
        description=f'Estorno da venda {sale.number}'[:180],
        amount=sale.total,
        payment_method=sale.payment_method,
        notes=f'Motivo: {reason}',
        created_by=user,
    )
    sale.status = Sale.Status.CANCELLED
    sale.payment_status = Sale.PaymentStatus.REFUNDED
    sale.reversal_cash_transaction = reversal
    sale.cancelled_at = timezone.now()
    sale.cancelled_by = user
    sale.cancellation_reason = reason
    sale.save(
        update_fields=(
            'status', 'payment_status', 'reversal_cash_transaction', 'cancelled_at',
            'cancelled_by', 'cancellation_reason', 'updated_at',
        )
    )
    return sale
