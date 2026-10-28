from django.test import TestCase

from .models import Category


class CategoryModelTests(TestCase):
    def test_category_uses_its_name_as_label(self):
        category = Category.objects.create(name='Vidros')

        self.assertEqual(str(category), 'Vidros')
