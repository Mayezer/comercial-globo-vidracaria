from django.contrib import admin

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


@admin.register(CashTransaction)
class CashTransactionAdmin(admin.ModelAdmin):
    list_display = ('transaction_date', 'kind', 'description', 'amount', 'payment_method', 'created_by')
    list_filter = ('kind', 'payment_method', 'transaction_date')
    list_select_related = ('created_by',)

    @staticmethod
    def _comes_from_sale(obj):
        return obj is not None and (
            hasattr(obj, 'sale_payment') or hasattr(obj, 'sale_reversal')
        )

    def get_readonly_fields(self, request, obj=None):
        if self._comes_from_sale(obj):
            return tuple(field.name for field in self.model._meta.fields)
        return super().get_readonly_fields(request, obj)

    def has_delete_permission(self, request, obj=None):
        if self._comes_from_sale(obj):
            return False
        return super().has_delete_permission(request, obj)


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'masked_cpf', 'monthly_salary', 'updated_at')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = ('expense_date', 'category', 'description', 'amount', 'supplier')
    list_filter = ('category', 'payment_method', 'expense_date')
    search_fields = ('description', 'notes')
    list_select_related = ('supplier', 'created_by', 'cash_transaction')


@admin.register(Payroll)
class PayrollAdmin(admin.ModelAdmin):
    list_display = ('competence', 'employee_name', 'gross_salary', 'net_salary', 'payment_date')
    list_filter = ('competence', 'payment_method')
    readonly_fields = ('employee_name', 'employee_cpf', 'cash_transaction', 'created_at', 'updated_at')


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ('name', 'masked_tax_id', 'contact_name', 'phone', 'is_active')
    list_filter = ('is_active',)


admin.site.register(SystemSettings)


admin.site.register(QuoteRequest)
admin.site.register(QuoteStatusHistory)
admin.site.register(QuoteAdminNotification)
