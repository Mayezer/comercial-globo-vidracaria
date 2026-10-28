from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, render

from .models import Service


def service_list(request):
    visible_services = Service.objects.filter(show_in_showcase=True)
    page_obj = Paginator(visible_services, 6).get_page(request.GET.get('page'))
    return render(
        request,
        'glazing_services/service_list.html',
        {'services': page_obj, 'page_obj': page_obj},
    )


def service_detail(request, pk):
    service = get_object_or_404(Service, pk=pk, show_in_showcase=True)
    return render(request, 'glazing_services/service_detail.html', {'service': service})
