from django.db import migrations, models
from django.db.models import F


def complete_shipping_orders(apps, schema_editor):
    orders = apps.get_model('main', 'TransactionHistory').objects.using(schema_editor.connection.alias)
    # Preserve the original seller confirmation time, including older rows without one.
    orders.filter(status='shipping', completed_at__isnull=True).update(completed_at=F('updated_at'))
    orders.filter(status='shipping').update(
        status='completed', status_message='Order completed via Insta ship.',
    )
    orders.filter(status='paid', status_message='Demo payment confirmed. Awaiting seller shipment.').update(
        status_message='Demo payment confirmed. Awaiting seller confirmation.',
    )


class Migration(migrations.Migration):
    dependencies = [
        ('main', '0021_seller_shipment_confirmation'),
    ]

    operations = [
        migrations.RenameField(
            model_name='transactionhistory', old_name='shipped_at', new_name='completed_at',
        ),
        migrations.RunPython(complete_shipping_orders, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='transactionhistory', name='status',
            field=models.CharField(
                choices=[('ongoing', 'Ongoing'), ('paid', 'Awaiting seller'), ('delivered', 'Delivered'),
                         ('completed', 'Completed'), ('cancelled', 'Cancelled')],
                default='ongoing', max_length=20,
            ),
        ),
    ]
