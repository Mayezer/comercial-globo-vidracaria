from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from accounts.models import Profile
from dashboard.models import CashTransaction, Employee, Payroll, QuoteRequest, Supplier, SystemSettings
from sales.models import Sale


MODEL_FIELDS = (
    (
        Profile,
        (
            'document', 'email', 'full_name', 'corporate_name', 'street', 'neighborhood',
            'house_number', 'reference_point', 'phone',
        ),
    ),
    (
        QuoteRequest,
        (
            'details', 'customer_name', 'customer_document', 'customer_email', 'customer_phone',
            'customer_street', 'customer_neighborhood', 'customer_house_number',
            'customer_reference_point',
        ),
    ),
    (CashTransaction, ('description', 'amount', 'notes')),
    (Employee, ('full_name', 'cpf', 'monthly_salary')),
    (Supplier, ('name', 'contact_name', 'tax_id', 'phone', 'email', 'address', 'notes')),
    (
        Payroll,
        ('employee_name', 'employee_cpf', 'gross_salary', 'additions', 'deductions', 'notes'),
    ),
    (SystemSettings, ('tax_id', 'phone', 'email', 'address', 'financial_manager')),
    (
        Sale,
        (
            'customer_name', 'customer_document', 'customer_contact', 'customer_email',
            'customer_address', 'notes', 'cancellation_reason',
        ),
    ),
)


class Command(BaseCommand):
    help = 'Recriptografa campos sensíveis com a versão ativa, sem remover chaves antigas.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--apply',
            action='store_true',
            help='Confirma a rotação. Sem esta opção o comando apenas informa a quantidade.',
        )
        parser.add_argument('--batch-size', type=int, default=200)

    def handle(self, *args, **options):
        batch_size = options['batch_size']
        if batch_size < 1 or batch_size > 5000:
            raise CommandError('--batch-size deve estar entre 1 e 5000.')
        total = sum(model.objects.count() for model, _ in MODEL_FIELDS)
        if not options['apply']:
            self.stdout.write(
                f'{total} registro(s) seriam recriptografados. Use --apply após o backup.'
            )
            return

        rotated = 0
        with transaction.atomic():
            for model, fields in MODEL_FIELDS:
                queryset = model.objects.select_for_update().order_by('pk')
                for instance in queryset.iterator(chunk_size=batch_size):
                    instance.save(update_fields=fields)
                    rotated += 1
        self.stdout.write(self.style.SUCCESS(f'{rotated} registro(s) recriptografados.'))
