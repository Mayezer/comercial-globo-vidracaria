from django.urls import path

from . import views


app_name = 'dashboard'

urlpatterns = [
    path('orcamento/solicitar/', views.request_quote, name='request_quote'),
    path('painel/', views.dashboard_home, name='home'),
    path('painel/administradores/', views.administrator_list, name='administrator_list'),
    path(
        'painel/administradores/novo/',
        views.administrator_create,
        name='administrator_create',
    ),
    path(
        'painel/administradores/<int:pk>/editar/',
        views.administrator_edit,
        name='administrator_edit',
    ),
    path('painel/orcamentos/', views.quote_list, name='quote_list'),
    path('painel/orcamentos/<int:pk>/', views.quote_detail, name='quote_detail'),
    path(
        'painel/orcamentos/<int:pk>/status/',
        views.update_quote_status,
        name='update_quote_status',
    ),
    path(
        'painel/notificacoes/proximo-orcamento/',
        views.next_quote_notification,
        name='next_quote_notification',
    ),
    path('painel/clientes/', views.customer_list, name='customer_list'),
    path('painel/clientes/<int:pk>/editar/', views.customer_edit, name='customer_edit'),
    path('painel/produtos/', views.product_list, name='product_list'),
    path('painel/produtos/novo/', views.product_form, name='product_create'),
    path('painel/produtos/saidas/', views.product_stock_exit, name='product_stock_exit'),
    path('painel/produtos/<int:pk>/editar/', views.product_form, name='product_edit'),
    path('painel/produtos/<int:pk>/excluir/', views.product_delete, name='product_delete'),
    path('painel/servicos/', views.service_list, name='service_list'),
    path('painel/servicos/novo/', views.service_form, name='service_create'),
    path('painel/servicos/<int:pk>/editar/', views.service_form, name='service_edit'),
    path('painel/servicos/<int:pk>/excluir/', views.service_delete, name='service_delete'),
    path('painel/caixa/', views.cash_daily, name='cash_daily'),
    path(
        'painel/caixa/novo/',
        views.cash_transaction_form,
        name='cash_transaction_create',
    ),
    path(
        'painel/caixa/<int:pk>/editar/',
        views.cash_transaction_form,
        name='cash_transaction_edit',
    ),
    path(
        'painel/caixa/<int:pk>/excluir/',
        views.cash_transaction_delete,
        name='cash_transaction_delete',
    ),
    path('painel/faturamento/', views.monthly_finance, name='monthly_finance'),
    path('painel/faturamento/pdf/', views.monthly_finance_pdf, name='monthly_finance_pdf'),
    path('painel/calculo-de-lucro/', views.profit_calculator, name='profit_calculator'),
    path('painel/gastos/', views.expense_list, name='expense_list'),
    path('painel/gastos/novo/', views.expense_form, name='expense_create'),
    path('painel/gastos/<int:pk>/editar/', views.expense_form, name='expense_edit'),
    path('painel/gastos/<int:pk>/excluir/', views.expense_delete, name='expense_delete'),
    path('painel/funcionarios/', views.employee_list, name='employee_list'),
    path('painel/funcionarios/novo/', views.employee_form, name='employee_create'),
    path('painel/funcionarios/<int:pk>/editar/', views.employee_form, name='employee_edit'),
    path('painel/funcionarios/<int:pk>/excluir/', views.employee_delete, name='employee_delete'),
    path('painel/folhas-de-pagamento/', views.payroll_list, name='payroll_list'),
    path('painel/folhas-de-pagamento/nova/', views.payroll_form, name='payroll_create'),
    path(
        'painel/folhas-de-pagamento/funcionario/<int:employee_pk>/criar/',
        views.payroll_quick_create,
        name='payroll_quick_create',
    ),
    path(
        'painel/folhas-de-pagamento/<int:pk>/editar/',
        views.payroll_form,
        name='payroll_edit',
    ),
    path(
        'painel/folhas-de-pagamento/<int:pk>/pdf/',
        views.payroll_pdf,
        name='payroll_pdf',
    ),
    path(
        'painel/folhas-de-pagamento/<int:pk>/excluir/',
        views.payroll_delete,
        name='payroll_delete',
    ),
    path('painel/fornecedores/', views.supplier_list, name='supplier_list'),
    path('painel/fornecedores/novo/', views.supplier_form, name='supplier_create'),
    path('painel/fornecedores/<int:pk>/editar/', views.supplier_form, name='supplier_edit'),
    path('painel/fornecedores/<int:pk>/excluir/', views.supplier_delete, name='supplier_delete'),
    path('painel/configuracoes/', views.system_settings, name='system_settings'),
]
