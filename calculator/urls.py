from django.urls import path

from . import views


app_name = 'calculator'

urlpatterns = [
    path('', views.calculator_home, name='home'),
    path('materiais/novo/', views.material_form, name='material_create'),
    path('materiais/<int:pk>/editar/', views.material_form, name='material_edit'),
    path('materiais/<int:pk>/excluir/', views.material_delete, name='material_delete'),
]
