from django.contrib import admin

from .models import Product, ProductStockExit


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'category', 'price', 'stock_quantity', 'show_in_showcase')
    list_filter = ('show_in_showcase', 'category')
    list_select_related = ('category',)
    ordering = ('name',)
    readonly_fields = ('id',)
    search_fields = ('name', 'description')
    autocomplete_fields = ('category',)
    fieldsets = (
        ('Identificação', {'fields': ('id', 'name', 'category')}),
        ('Venda e estoque', {'fields': ('price', 'stock_quantity')}),
        ('Apresentação', {'fields': ('show_in_showcase', 'photo', 'description')}),
    )


@admin.register(ProductStockExit)
class ProductStockExitAdmin(admin.ModelAdmin):
    list_display = ('id', 'product_name', 'quantity', 'stock_before', 'stock_after', 'created_at')
    list_select_related = ('product', 'created_by')
    ordering = ('-created_at', '-id')
    readonly_fields = (
        'product',
        'product_name',
        'quantity',
        'stock_before',
        'stock_after',
        'notes',
        'created_by',
        'created_at',
    )
    search_fields = ('product_name', 'notes', 'created_by__username')

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
