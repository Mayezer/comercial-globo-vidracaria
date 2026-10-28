from django.urls import path

from . import views


app_name = 'sales'

urlpatterns = [
    path('', views.sale_list, name='list'),
    path('nova/', views.sale_create, name='create'),
    path('<int:pk>/', views.sale_detail, name='detail'),
    path('<int:pk>/editar/', views.sale_edit, name='edit'),
    path('<int:pk>/itens/<int:item_pk>/remover/', views.sale_item_remove, name='item_remove'),
    path('<int:pk>/conferir/', views.sale_review, name='review'),
    path('<int:pk>/concluir/', views.sale_complete, name='complete'),
    path('<int:pk>/cancelar/', views.sale_cancel, name='cancel'),
]
