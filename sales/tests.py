from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from accounts.models import Profile
from calculator.models import Material
from categories.models import Category
from dashboard.models import CashTransaction
from glazing_services.models import Service
from products.models import Product, ProductStockExit

from .forms import SaleForm
from .models import Sale, SaleItem, SaleStockMovement
from .services import cancel_sale, complete_sale


User = get_user_model()


class SalesPhaseOneTests(TestCase):
    password = 'Senha-Forte-2026'

    def setUp(self):
        self.staff = User.objects.create_superuser(
            username='sales-admin', email='sales@example.com', password=self.password
        )
        self.regular_user = User.objects.create_user(
            username='sales-customer', email='customer@example.com', password=self.password
        )
        self.category = Category.objects.create(name='Ferragens')
        self.product = Product.objects.create(
            name='Kit de roldanas', category=self.category,
            price=Decimal('40.00'), stock_quantity=10,
        )
        self.material = Material.objects.create(
            name='Vidro temperado 8 mm',
            unit_type=Material.UnitType.SQUARE_METER,
            unit_price=Decimal('100.00'),
        )
        self.service = Service.objects.create(
            name='Instalação de box', service_type='Instalação'
        )

    def create_sale(self, *, quantity=2, stock_product=None):
        product = stock_product or self.product
        sale = Sale.objects.create(
            employee=self.staff,
            customer_type=Sale.CustomerType.WALK_IN_ANONYMOUS,
            customer_name='Cliente Balcão',
            payment_method=CashTransaction.PaymentMethod.PIX,
        )
        SaleItem.objects.create(
            sale=sale,
            item_type=SaleItem.ItemType.PRODUCT,
            product=product,
            description=product.name,
            unit=SaleItem.Unit.UNIT,
            quantity=Decimal(quantity),
            unit_price=product.price,
        )
        sale.recalculate_totals(save=True)
        sale.amount_paid = sale.total
        sale.save(update_fields=('amount_paid', 'updated_at'))
        return sale

    def test_square_meter_calculation_uses_millimeters_and_decimal(self):
        sale = Sale.objects.create(
            employee=self.staff,
            customer_type=Sale.CustomerType.WALK_IN_ANONYMOUS,
            customer_name='Cliente Balcão',
        )
        item = SaleItem.objects.create(
            sale=sale,
            item_type=SaleItem.ItemType.MATERIAL,
            material=self.material,
            description=self.material.name,
            unit=SaleItem.Unit.SQUARE_METER,
            quantity=Decimal('1'),
            width_mm=Decimal('1250'),
            height_mm=Decimal('800'),
            piece_count=3,
            unit_price=Decimal('100.00'),
        )

        self.assertEqual(item.area_sqm, Decimal('3.000000'))
        self.assertEqual(item.quantity, Decimal('3.000000'))
        self.assertEqual(item.total, Decimal('300.00'))

    def test_money_is_rounded_only_after_precise_area_calculation(self):
        sale = Sale.objects.create(
            employee=self.staff,
            customer_type=Sale.CustomerType.WALK_IN_ANONYMOUS,
            customer_name='Cliente Balcão',
        )
        item = SaleItem.objects.create(
            sale=sale,
            item_type=SaleItem.ItemType.MATERIAL,
            material=self.material,
            description=self.material.name,
            unit=SaleItem.Unit.SQUARE_METER,
            quantity=Decimal('1'),
            width_mm=Decimal('333'),
            height_mm=Decimal('333'),
            piece_count=1,
            unit_price=Decimal('100.00'),
        )

        self.assertEqual(item.area_sqm, Decimal('0.110889'))
        self.assertEqual(item.total, Decimal('11.09'))

    def test_registered_customer_and_catalog_data_are_frozen(self):
        customer_user = User.objects.create_user(
            username='52998224725', email='maria@example.com', password=self.password
        )
        profile = Profile.objects.create(
            user=customer_user,
            account_type=Profile.AccountType.INDIVIDUAL,
            document='52998224725',
            email='maria@example.com',
            full_name='Maria da Silva',
            phone='11999999999',
            street='Rua A', neighborhood='Centro', house_number='10',
        )
        sale = Sale.objects.create(
            employee=self.staff,
            customer_type=Sale.CustomerType.REGISTERED,
            customer=profile,
            customer_name='',
            payment_method=CashTransaction.PaymentMethod.CASH,
        )
        item = SaleItem.objects.create(
            sale=sale,
            item_type=SaleItem.ItemType.PRODUCT,
            product=self.product,
            description=self.product.name,
            unit=SaleItem.Unit.UNIT,
            quantity=Decimal('1'),
            unit_price=self.product.price,
        )
        sale.recalculate_totals(save=True)
        sale.amount_paid = sale.total
        sale.save(update_fields=('amount_paid', 'updated_at'))

        complete_sale(sale.pk, self.staff)
        profile.full_name = 'Nome alterado depois'
        profile.save(update_fields=('full_name',))
        self.product.name = 'Produto renomeado depois'
        self.product.price = Decimal('999.00')
        self.product.save(update_fields=('name', 'price'))
        sale.refresh_from_db()
        item.refresh_from_db()

        self.assertEqual(sale.customer_name, 'Maria da Silva')
        self.assertEqual(sale.customer_document, '52998224725')
        self.assertEqual(item.description, 'Kit de roldanas')
        self.assertEqual(item.unit_price, Decimal('40.00'))

    def test_walk_in_identified_and_anonymous_do_not_create_profiles(self):
        initial_profiles = Profile.objects.count()
        identified_form = SaleForm(data={
            'customer_type': Sale.CustomerType.WALK_IN_IDENTIFIED,
            'customer_name': 'João do Balcão',
            'customer_document': '529.982.247-25',
            'customer_contact': '(11) 99999-9999',
            'discount': '0,00',
            'payment_method': '',
            'amount_paid': '0,00',
            'notes': '',
        })
        self.assertTrue(identified_form.is_valid(), identified_form.errors)
        identified = identified_form.save(employee=self.staff)

        anonymous_form = SaleForm(data={
            'customer_type': Sale.CustomerType.WALK_IN_ANONYMOUS,
            'customer_name': '', 'customer_document': '', 'customer_contact': '',
            'discount': '0,00', 'payment_method': '', 'amount_paid': '0,00', 'notes': '',
        })
        self.assertTrue(anonymous_form.is_valid(), anonymous_form.errors)
        anonymous = anonymous_form.save(employee=self.staff)

        self.assertEqual(Profile.objects.count(), initial_profiles)
        self.assertIsNone(identified.customer_id)
        self.assertEqual(identified.customer_name, 'João do Balcão')
        self.assertEqual(identified.customer_document, '52998224725')
        self.assertIsNone(anonymous.customer_id)
        self.assertEqual(anonymous.customer_name, 'Cliente Balcão')

    def test_all_three_item_types_can_be_part_of_the_same_sale(self):
        sale = self.create_sale(quantity=1)
        SaleItem.objects.create(
            sale=sale, item_type=SaleItem.ItemType.MATERIAL, material=self.material,
            description=self.material.name, unit=SaleItem.Unit.SQUARE_METER,
            quantity=Decimal('1'), width_mm=Decimal('1000'), height_mm=Decimal('500'),
            piece_count=2, unit_price=Decimal('100.00'),
        )
        SaleItem.objects.create(
            sale=sale, item_type=SaleItem.ItemType.SERVICE, service=self.service,
            description=self.service.name, unit=SaleItem.Unit.SERVICE,
            quantity=Decimal('1'), unit_price=Decimal('75.00'),
        )
        sale.recalculate_totals(save=True)
        sale.amount_paid = sale.total
        sale.save(update_fields=('amount_paid', 'updated_at'))

        complete_sale(sale.pk, self.staff)
        sale.refresh_from_db()

        self.assertEqual(sale.items.count(), 3)
        self.assertEqual(sale.total, Decimal('215.00'))
        self.assertEqual(sale.status, Sale.Status.COMPLETED)

    def test_insufficient_stock_prevents_every_part_of_completion(self):
        sale = self.create_sale(quantity=11)

        with self.assertRaisesMessage(ValidationError, 'Estoque insuficiente'):
            complete_sale(sale.pk, self.staff)

        sale.refresh_from_db()
        self.product.refresh_from_db()
        self.assertEqual(sale.status, Sale.Status.DRAFT)
        self.assertEqual(self.product.stock_quantity, 10)
        self.assertEqual(CashTransaction.objects.count(), 0)
        self.assertEqual(ProductStockExit.objects.count(), 0)
        self.assertEqual(SaleStockMovement.objects.count(), 0)

    def test_completion_is_atomic_when_stock_history_write_fails(self):
        sale = self.create_sale(quantity=2)

        with patch('sales.services.ProductStockExit.objects.create', side_effect=RuntimeError('falha')):
            with self.assertRaises(RuntimeError):
                complete_sale(sale.pk, self.staff)

        sale.refresh_from_db()
        self.product.refresh_from_db()
        self.assertEqual(sale.status, Sale.Status.DRAFT)
        self.assertEqual(self.product.stock_quantity, 10)
        self.assertEqual(CashTransaction.objects.count(), 0)
        self.assertEqual(SaleStockMovement.objects.count(), 0)

    def test_completion_creates_cash_and_stock_history_only_once(self):
        sale = self.create_sale(quantity=2)

        complete_sale(sale.pk, self.staff)
        complete_sale(sale.pk, self.staff)
        sale.refresh_from_db()
        self.product.refresh_from_db()

        self.assertEqual(sale.status, Sale.Status.COMPLETED)
        self.assertEqual(sale.payment_status, Sale.PaymentStatus.PAID)
        self.assertEqual(self.product.stock_quantity, 8)
        self.assertEqual(CashTransaction.objects.count(), 1)
        self.assertEqual(ProductStockExit.objects.count(), 1)
        self.assertEqual(
            SaleStockMovement.objects.filter(kind=SaleStockMovement.Kind.EXIT).count(), 1
        )

    def test_paid_amount_must_exactly_match_sale_total(self):
        sale = self.create_sale(quantity=1)
        sale.amount_paid = Decimal('39.99')
        sale.save(update_fields=('amount_paid', 'updated_at'))

        with self.assertRaisesMessage(ValidationError, 'total pago'):
            complete_sale(sale.pk, self.staff)

        self.assertEqual(CashTransaction.objects.count(), 0)

    def test_cancellation_restores_stock_and_creates_auditable_reversal_once(self):
        sale = self.create_sale(quantity=3)
        complete_sale(sale.pk, self.staff)
        original_cash_id = Sale.objects.get(pk=sale.pk).cash_transaction_id

        cancel_sale(sale.pk, self.staff, 'Cliente desistiu da compra')
        cancel_sale(sale.pk, self.staff, 'Tentativa repetida')
        sale.refresh_from_db()
        self.product.refresh_from_db()

        self.assertEqual(sale.status, Sale.Status.CANCELLED)
        self.assertEqual(sale.payment_status, Sale.PaymentStatus.REFUNDED)
        self.assertEqual(sale.cancellation_reason, 'Cliente desistiu da compra')
        self.assertEqual(self.product.stock_quantity, 10)
        self.assertTrue(CashTransaction.objects.filter(pk=original_cash_id).exists())
        self.assertEqual(CashTransaction.objects.count(), 2)
        self.assertEqual(
            SaleStockMovement.objects.filter(kind=SaleStockMovement.Kind.RETURN).count(), 1
        )

    def test_cancelled_sale_cannot_be_completed_or_edited(self):
        sale = self.create_sale(quantity=1)
        complete_sale(sale.pk, self.staff)
        cancel_sale(sale.pk, self.staff, 'Cadastro duplicado')

        with self.assertRaisesMessage(ValidationError, 'cancelada'):
            complete_sale(sale.pk, self.staff)
        item = sale.items.get()
        item.description = 'Alteração indevida'
        with self.assertRaises(ValidationError):
            item.save()

    def test_sales_pages_follow_staff_permission_pattern(self):
        list_url = reverse('sales:list')
        create_url = reverse('sales:create')
        anonymous = self.client.get(list_url)
        self.assertRedirects(anonymous, f'{reverse("accounts:login")}?next={list_url}')

        self.client.force_login(self.regular_user)
        self.assertEqual(self.client.get(list_url).status_code, 403)
        self.assertEqual(self.client.get(create_url).status_code, 403)

        self.client.force_login(self.staff)
        response = self.client.get(list_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Vendas')
        self.assertContains(response, reverse('sales:create'))

    def test_sale_workflow_pages_render_for_staff(self):
        sale = self.create_sale(quantity=1)
        self.client.force_login(self.staff)

        for url in (
            reverse('sales:create'),
            reverse('sales:edit', args=[sale.pk]),
            reverse('sales:review', args=[sale.pk]),
        ):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

        complete_sale(sale.pk, self.staff)
        self.assertEqual(self.client.get(reverse('sales:detail', args=[sale.pk])).status_code, 200)
        self.assertEqual(self.client.get(reverse('sales:cancel', args=[sale.pk])).status_code, 200)

    def test_sale_form_rejects_discount_above_current_subtotal(self):
        sale = self.create_sale(quantity=1)
        form = SaleForm(instance=sale, data={
            'customer_type': Sale.CustomerType.WALK_IN_ANONYMOUS,
            'customer_name': '', 'customer_document': '', 'customer_contact': '',
            'discount': '40,01', 'payment_method': CashTransaction.PaymentMethod.PIX,
            'amount_paid': '40,00', 'notes': '',
        })

        self.assertFalse(form.is_valid())
        self.assertIn('subtotal atual', form.errors['discount'][0])

    def test_sale_cash_entries_cannot_be_edited_or_deleted_directly(self):
        sale = self.create_sale(quantity=1)
        complete_sale(sale.pk, self.staff)
        sale.refresh_from_db()
        self.client.force_login(self.staff)

        edit_response = self.client.get(
            reverse('dashboard:cash_transaction_edit', args=[sale.cash_transaction_id])
        )
        delete_response = self.client.post(
            reverse('dashboard:cash_transaction_delete', args=[sale.cash_transaction_id])
        )

        self.assertRedirects(edit_response, reverse('sales:detail', args=[sale.pk]))
        self.assertEqual(delete_response.status_code, 302)
        self.assertTrue(CashTransaction.objects.filter(pk=sale.cash_transaction_id).exists())
