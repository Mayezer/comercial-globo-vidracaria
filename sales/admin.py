from django.contrib import admin

from .models import Sale, SaleItem, SaleStockMovement


class SaleItemInline(admin.TabularInline):
    model = SaleItem
    extra = 0
    can_delete = False
    readonly_fields = (
        'item_type', 'description', 'unit', 'quantity', 'unit_price', 'discount', 'total',
        'width_mm', 'height_mm', 'piece_count', 'area_sqm',
    )


@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = ('number', 'customer_name', 'status', 'payment_status', 'total', 'created_at')
    list_filter = ('status', 'customer_type', 'payment_status', 'payment_method')
    list_select_related = ('employee', 'customer')
    readonly_fields = (
        'status', 'employee', 'customer_type', 'customer', 'customer_name', 'customer_document',
        'customer_contact', 'customer_email', 'customer_address', 'subtotal', 'discount', 'total',
        'payment_method', 'payment_status', 'amount_paid', 'notes', 'cash_transaction',
        'reversal_cash_transaction', 'created_at', 'updated_at', 'completed_at', 'cancelled_at',
        'cancelled_by', 'cancellation_reason',
    )
    inlines = (SaleItemInline,)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(SaleStockMovement)
class SaleStockMovementAdmin(admin.ModelAdmin):
    list_display = ('sale', 'product', 'kind', 'quantity', 'stock_before', 'stock_after', 'created_at')
    list_filter = ('kind',)
    readonly_fields = [field.name for field in SaleStockMovement._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
