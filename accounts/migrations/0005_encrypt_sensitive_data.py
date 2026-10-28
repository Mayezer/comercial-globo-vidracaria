import uuid

from django.db import migrations


def protect_sensitive_data(apps, schema_editor):
    from accounts.models import normalize_text, only_digits
    from app.crypto import active_encryption_key, blind_index, hash_key

    # Falha antes da primeira gravação se os segredos não estiverem disponíveis.
    active_encryption_key()
    hash_key()

    Profile = apps.get_model('accounts', 'Profile')
    for profile in Profile.objects.select_related('user').iterator(chunk_size=500):
        profile.document = only_digits(profile.document)
        profile.email = profile.email.strip().lower()
        profile.full_name = (profile.full_name or '').strip()
        profile.corporate_name = (profile.corporate_name or '').strip()
        profile.phone = only_digits(profile.phone)
        profile.document_hash = blind_index(profile.document, 'profile.document')
        profile.email_hash = blind_index(profile.email, 'profile.email')
        profile.full_name_hash = blind_index(normalize_text(profile.full_name), 'profile.full_name')
        profile.corporate_name_hash = blind_index(
            normalize_text(profile.corporate_name), 'profile.corporate_name'
        )
        profile.phone_hash = blind_index(profile.phone, 'profile.phone')
        profile.save(
            update_fields=(
                'document', 'document_hash', 'email', 'email_hash', 'full_name',
                'full_name_hash', 'corporate_name', 'corporate_name_hash', 'street',
                'neighborhood', 'house_number', 'reference_point', 'phone', 'phone_hash',
            )
        )
        user = profile.user
        user.username = f'acct_{uuid.uuid5(uuid.NAMESPACE_URL, f"globo-profile:{profile.pk}").hex}'
        user.email = ''
        user.save(update_fields=('username', 'email'))

    QuoteRequest = apps.get_model('dashboard', 'QuoteRequest')
    quote_fields = (
        'details', 'customer_name', 'customer_document', 'customer_email', 'customer_phone',
        'customer_street', 'customer_neighborhood', 'customer_house_number',
        'customer_reference_point',
    )
    for quote in QuoteRequest.objects.all().iterator(chunk_size=500):
        quote.save(update_fields=quote_fields)

    CashTransaction = apps.get_model('dashboard', 'CashTransaction')
    for item in CashTransaction.objects.all().iterator(chunk_size=500):
        item.save(update_fields=('description', 'notes'))

    Employee = apps.get_model('dashboard', 'Employee')
    for employee in Employee.objects.all().iterator(chunk_size=500):
        employee.cpf = only_digits(employee.cpf)
        employee.full_name = (employee.full_name or '').strip()
        employee.full_name_hash = blind_index(normalize_text(employee.full_name), 'employee.full_name')
        employee.cpf_hash = blind_index(employee.cpf, 'employee.cpf')
        employee.save(
            update_fields=('full_name', 'full_name_hash', 'cpf', 'cpf_hash', 'monthly_salary')
        )

    Supplier = apps.get_model('dashboard', 'Supplier')
    for supplier in Supplier.objects.all().iterator(chunk_size=500):
        supplier.name = (supplier.name or '').strip()
        supplier.contact_name = (supplier.contact_name or '').strip()
        supplier.tax_id = only_digits(supplier.tax_id)
        supplier.phone = only_digits(supplier.phone)
        supplier.email = (supplier.email or '').strip().lower()
        supplier.name_hash = blind_index(normalize_text(supplier.name), 'supplier.name')
        supplier.contact_name_hash = blind_index(
            normalize_text(supplier.contact_name), 'supplier.contact_name'
        )
        supplier.tax_id_hash = blind_index(supplier.tax_id, 'supplier.tax_id')
        supplier.phone_hash = blind_index(supplier.phone, 'supplier.phone')
        supplier.email_hash = blind_index(supplier.email, 'supplier.email')
        supplier.save(
            update_fields=(
                'name', 'name_hash', 'contact_name', 'contact_name_hash', 'tax_id',
                'tax_id_hash', 'phone', 'phone_hash', 'email', 'email_hash', 'address', 'notes',
            )
        )

    Payroll = apps.get_model('dashboard', 'Payroll')
    for payroll in Payroll.objects.all().iterator(chunk_size=500):
        payroll.employee_cpf = only_digits(payroll.employee_cpf)
        payroll.employee_cpf_hash = blind_index(
            payroll.employee_cpf, 'payroll.employee_cpf'
        )
        payroll.save(
            update_fields=(
                'employee_name', 'employee_cpf', 'employee_cpf_hash', 'gross_salary',
                'additions', 'deductions', 'notes',
            )
        )

    SystemSettings = apps.get_model('dashboard', 'SystemSettings')
    for system_settings in SystemSettings.objects.all().iterator(chunk_size=50):
        system_settings.tax_id = only_digits(system_settings.tax_id)
        system_settings.tax_id_hash = blind_index(
            system_settings.tax_id, 'system_settings.tax_id'
        )
        system_settings.save(
            update_fields=(
                'tax_id', 'tax_id_hash', 'phone', 'email', 'address', 'financial_manager',
            )
        )

    Sale = apps.get_model('sales', 'Sale')
    for sale in Sale.objects.all().iterator(chunk_size=500):
        sale.customer_name = (sale.customer_name or '').strip()
        sale.customer_document = only_digits(sale.customer_document)
        sale.customer_contact = (sale.customer_contact or '').strip()
        sale.customer_email = (sale.customer_email or '').strip().lower()
        sale.customer_name_hash = blind_index(
            normalize_text(sale.customer_name), 'sale.customer_name'
        )
        sale.customer_document_hash = blind_index(
            sale.customer_document, 'sale.customer_document'
        )
        sale.customer_contact_hash = blind_index(
            normalize_text(sale.customer_contact), 'sale.customer_contact'
        )
        sale.customer_email_hash = blind_index(sale.customer_email, 'sale.customer_email')
        sale.save(
            update_fields=(
                'customer_name', 'customer_name_hash', 'customer_document',
                'customer_document_hash', 'customer_contact', 'customer_contact_hash',
                'customer_email', 'customer_email_hash', 'customer_address', 'notes',
                'cancellation_reason',
            )
        )


def _decrypt_table(schema_editor, table, field_contexts):
    from app.crypto import decrypt_value

    quote_name = schema_editor.connection.ops.quote_name
    columns = list(field_contexts)
    select_columns = ', '.join(quote_name(column) for column in ('id', *columns))
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(f'SELECT {select_columns} FROM {quote_name(table)}')
        rows = cursor.fetchall()
        assignments = ', '.join(f'{quote_name(column)} = %s' for column in columns)
        for row in rows:
            plaintext = [
                decrypt_value(value, field_contexts[column])
                for column, value in zip(columns, row[1:])
            ]
            cursor.execute(
                f'UPDATE {quote_name(table)} SET {assignments} WHERE {quote_name("id")} = %s',
                [*plaintext, row[0]],
            )


def restore_plaintext_data(apps, schema_editor):
    tables = {
        'accounts_profile': {
            field: f'accounts.profile.{field}'
            for field in (
                'document', 'email', 'full_name', 'corporate_name', 'street', 'neighborhood',
                'house_number', 'reference_point', 'phone',
            )
        },
        'dashboard_quoterequest': {
            field: f'dashboard.quoterequest.{field}'
            for field in (
                'details', 'customer_name', 'customer_document', 'customer_email',
                'customer_phone', 'customer_street', 'customer_neighborhood',
                'customer_house_number', 'customer_reference_point',
            )
        },
        'dashboard_cashtransaction': {
            field: f'dashboard.cashtransaction.{field}' for field in ('description', 'notes')
        },
        'dashboard_employee': {
            field: f'dashboard.employee.{field}' for field in ('full_name', 'cpf', 'monthly_salary')
        },
        'dashboard_supplier': {
            field: f'dashboard.supplier.{field}'
            for field in ('name', 'contact_name', 'tax_id', 'phone', 'email', 'address', 'notes')
        },
        'dashboard_payroll': {
            field: f'dashboard.payroll.{field}'
            for field in (
                'employee_name', 'employee_cpf', 'gross_salary', 'additions', 'deductions', 'notes',
            )
        },
        'dashboard_systemsettings': {
            field: f'dashboard.systemsettings.{field}'
            for field in ('tax_id', 'phone', 'email', 'address', 'financial_manager')
        },
        'sales_sale': {
            field: f'sales.sale.{field}'
            for field in (
                'customer_name', 'customer_document', 'customer_contact', 'customer_email',
                'customer_address', 'notes', 'cancellation_reason',
            )
        },
    }
    for table, field_contexts in tables.items():
        _decrypt_table(schema_editor, table, field_contexts)

    Profile = apps.get_model('accounts', 'Profile')
    for profile in Profile.objects.select_related('user').iterator(chunk_size=500):
        user = profile.user
        user.username = profile.document
        user.email = profile.email
        user.save(update_fields=('username', 'email'))


class Migration(migrations.Migration):
    dependencies = [
        ('accounts', '0004_profile_corporate_name_hash_profile_document_hash_and_more'),
        ('dashboard', '0004_alter_employee_options_alter_payroll_options_and_more'),
        ('sales', '0003_sale_customer_contact_hash_and_more'),
    ]

    operations = [
        migrations.RunPython(protect_sensitive_data, restore_plaintext_data),
    ]
