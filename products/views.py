from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, render

from .models import Product


def product_list(request):
    products = Product.objects.select_related('category').filter(show_in_showcase=True)
    page_obj = Paginator(products, 6).get_page(request.GET.get('page'))
    return render(
        request,
        'products/product_list.html',
        {'products': page_obj, 'page_obj': page_obj},
    )


def product_detail(request, pk):
    product = get_object_or_404(
        Product.objects.select_related('category'),
        pk=pk,
        show_in_showcase=True,
    )
    return render(request, 'products/product_detail.html', {'product': product})
