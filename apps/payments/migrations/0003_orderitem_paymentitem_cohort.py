import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("courses", "0028_cohort_enrollment_open"),
        ("payments", "0002_order_payment_order_orderitem_paymentinstallment_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="orderitem",
            name="cohort",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="order_items",
                to="courses.cohort",
            ),
        ),
        migrations.AddField(
            model_name="paymentitem",
            name="cohort",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="payment_items",
                to="courses.cohort",
            ),
        ),
    ]
