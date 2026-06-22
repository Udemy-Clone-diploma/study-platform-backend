# Generated manually to align cart items with course pricing plans.

import django.db.models.deletion
from django.db import migrations, models


def assign_cheapest_pricing_plan(apps, schema_editor):
    cart_item_model = apps.get_model("cart", "CartItem")
    pricing_plan_model = apps.get_model("courses", "PricingPlan")

    for item in cart_item_model.objects.filter(pricing_plan__isnull=True):
        plan = (
            pricing_plan_model.objects.filter(course_id=item.course_id)
            .order_by("price", "id")
            .first()
        )
        if plan is not None:
            item.pricing_plan_id = plan.id
            item.save(update_fields=["pricing_plan"])


class Migration(migrations.Migration):
    dependencies = [
        ("courses", "0021_course_moderator_comment"),
        ("cart", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="cartitem",
            name="pricing_plan",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="cart_items",
                to="courses.pricingplan",
            ),
        ),
        migrations.RunPython(assign_cheapest_pricing_plan, migrations.RunPython.noop),
    ]
