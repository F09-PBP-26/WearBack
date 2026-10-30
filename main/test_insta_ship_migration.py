from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase
from django.utils import timezone


class InstaShipCompletionMigrationTests(TransactionTestCase):
    def restore_latest_schema(self):
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())

    def test_shipping_orders_become_completed_and_unconfirmed_payments_stay_paid(self):
        self.addCleanup(self.restore_latest_schema)
        executor = MigrationExecutor(connection)
        before = [('main', '0020_transaction_shipping_status')]
        executor.migrate(before)
        old_apps = executor.loader.project_state(before).apps
        User = old_apps.get_model('main', 'User')
        Listing = old_apps.get_model('listings', 'Listing')
        Order = old_apps.get_model('main', 'TransactionHistory')
        buyer = User.objects.create(username='completion-migration-buyer')
        seller = User.objects.create(username='completion-migration-seller')
        listing = Listing.objects.create(seller_id=seller.pk, name='Migration jacket', price=150000)
        automatic = Order.objects.create(
            buyer_id=buyer.pk, listing_id=listing.pk, item_name='Unconfirmed automatic shipping', price=150000,
            status='shipping', status_message='Demo payment confirmed. Insta ship is active.',
        )

        intermediate = [('main', '0021_seller_shipment_confirmation')]
        executor = MigrationExecutor(connection)
        executor.migrate(intermediate)
        Order = executor.loader.project_state(intermediate).apps.get_model('main', 'TransactionHistory')
        self.assertEqual(Order.objects.get(pk=automatic.pk).status, 'paid')
        confirmed_at = timezone.now()
        confirmed = Order.objects.create(
            buyer_id=buyer.pk, listing_id=listing.pk, item_name='Seller confirmed shipping', price=150000,
            status='shipping', status_message='Seller confirmed shipment via Insta ship.', shipped_at=confirmed_at,
        )
        missing_time = Order.objects.create(
            buyer_id=buyer.pk, listing_id=listing.pk, item_name='Older shipping order', price=150000,
            status='shipping',
        )
        unchanged = []
        for status in ('ongoing', 'paid', 'delivered', 'completed', 'cancelled'):
            order = Order.objects.create(
                buyer_id=buyer.pk, listing_id=listing.pk, item_name=status, price=150000,
                status=status, status_message='Preserve this update',
            )
            unchanged.append((order.pk, status))

        after = [('main', '0022_insta_ship_completes_orders')]
        executor = MigrationExecutor(connection)
        executor.migrate(after)
        Order = executor.loader.project_state(after).apps.get_model('main', 'TransactionHistory')
        confirmed_order = Order.objects.get(pk=confirmed.pk)
        self.assertEqual(confirmed_order.status, 'completed')
        self.assertEqual(confirmed_order.completed_at, confirmed_at)
        self.assertEqual(confirmed_order.status_message, 'Order completed via Insta ship.')
        older_order = Order.objects.get(pk=missing_time.pk)
        self.assertEqual(older_order.status, 'completed')
        self.assertEqual(older_order.completed_at, missing_time.updated_at)
        automatic_order = Order.objects.get(pk=automatic.pk)
        self.assertEqual(automatic_order.status, 'paid')
        self.assertIsNone(automatic_order.completed_at)
        self.assertEqual(automatic_order.status_message, 'Demo payment confirmed. Awaiting seller confirmation.')
        for pk, status in unchanged:
            with self.subTest(status=status):
                order = Order.objects.get(pk=pk)
                self.assertEqual(order.status, status)
                self.assertIsNone(order.completed_at)
                self.assertEqual(order.status_message, 'Preserve this update')
        self.assertFalse(Order.objects.filter(status='shipping').exists())
