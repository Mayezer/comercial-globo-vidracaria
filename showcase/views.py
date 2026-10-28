from django.shortcuts import render

from products.models import Product


def home(request):
    featured_products = (
        Product.objects.select_related('category')
        .filter(show_in_showcase=True)
        .order_by('-id')[:6]
    )
    return render(
        request,
        'showcase/home.html',
        {'featured_products': featured_products},
    )
