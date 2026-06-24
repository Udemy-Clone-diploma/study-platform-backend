import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("cart", "0002_cartitem_pricing_plan"),
        ("courses", "0028_cohort_enrollment_open"),
    ]

    operations = [
        migrations.AddField(
            model_name="cartitem",
            name="cohort",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="cart_items",
                to="courses.cohort",
            ),
        ),
    ]
