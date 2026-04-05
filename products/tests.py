from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import TestCase

from products.models import Product


class LifeCycleModelTests(TestCase):
    def test_save_validates_required_fields(self):
        product = Product(name="iPhone", description="Desc")

        with self.assertRaises(ValidationError) as exc:
            product.save()

        self.assertIn("price", exc.exception.message_dict)

    def test_before_save_callbacks_run_and_skip_static_callback(self):
        product = Product(name="iPhone", description="Desc", price="10.00")

        with patch("builtins.print") as mocked_print:
            product.save()

        printed_messages = [args[0] for args, _ in mocked_print.call_args_list]
        self.assertNotIn("Sending email for product iPhone", printed_messages)
        self.assertIn("Calculating total for product iPhone", printed_messages)
        self.assertIn("Updating category for product iPhone", printed_messages)

    def test_skip_hooks_context_manager_skips_specific_callback(self):
        product = Product(name="iPhone", description="Desc", price="10.00")

        with patch("builtins.print") as mocked_print:
            with product.skip_hooks("calculate_total"):
                product.save()

        printed_messages = [args[0] for args, _ in mocked_print.call_args_list]
        self.assertNotIn(
            "Calculating total for product iPhone",
            printed_messages,
        )
        self.assertIn("Updating category for product iPhone", printed_messages)

    def test_partial_update_does_not_validate_unrelated_fields(self):
        product = Product.objects.create(
            name="Phone",
            description="Desc",
            price="99.00",
        )
        product.price = None
        product.name = "Updated Phone"

        # update_fields limits validation to persisted fields.
        product.save(update_fields=["name"])
        product.refresh_from_db()

        self.assertEqual(product.name, "Updated Phone")

    def test_delete_callbacks_run(self):
        product = Product.objects.create(
            name="Phone",
            description="Desc",
            price="99.00",
        )

        with patch("builtins.print") as mocked_print:
            product.delete()

        printed_messages = [args[0] for args, _ in mocked_print.call_args_list]
        self.assertIn(
            "Sending email for product Phone before delete",
            printed_messages,
        )
        self.assertIn(
            "Sending email for product Phone after delete",
            printed_messages,
        )
