from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from dashboard.decorators import staff_required

from .forms import MaterialForm
from .models import Material


@staff_required
def calculator_home(request):
    return render(
        request,
        'calculator/calculator.html',
        {'materials': Material.objects.all()},
    )


@staff_required
def material_form(request, pk=None):
    material = get_object_or_404(Material, pk=pk) if pk is not None else None
    form = MaterialForm(request.POST or None, instance=material)
    if request.method == 'POST' and form.is_valid():
        material = form.save()
        messages.success(request, f'Material “{material.name}” salvo com sucesso.')
        if 'save_and_add_another' in request.POST:
            return redirect('calculator:material_create')
        return redirect('calculator:home')
    return render(
        request,
        'calculator/material_form.html',
        {'form': form, 'material': material},
    )


@require_POST
@staff_required
def material_delete(request, pk):
    material = get_object_or_404(Material, pk=pk)
    material_name = material.name
    material.delete()
    messages.success(request, f'Material “{material_name}” excluído com sucesso.')
    return redirect('calculator:home')
