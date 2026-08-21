from decimal import Decimal
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("payments", "0004_orderitem_schedule_slots_paymentitem_schedule_slots"), ("users", "0021_merge_20260725_1221")]
    operations = [
        migrations.CreateModel(
            name="TeacherPayoutAccount",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("provider", models.CharField(default="stripe", max_length=20)),
                ("provider_account_id", models.CharField(max_length=255, unique=True)),
                ("status", models.CharField(choices=[("incomplete", "Setup incomplete"), ("pending", "Verification pending"), ("active", "Active"), ("restricted", "Restricted")], default="incomplete", max_length=24)),
                ("details_submitted", models.BooleanField(default=False)),
                ("charges_enabled", models.BooleanField(default=False)),
                ("payouts_enabled", models.BooleanField(default=False)),
                ("country", models.CharField(blank=True, default="", max_length=2)),
                ("outstanding_requirements", models.JSONField(blank=True, default=list)),
                ("disabled_reason", models.CharField(blank=True, default="", max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("teacher", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="payout_account", to="users.teacherprofile")),
            ], options={"db_table": "teacher_payout_accounts"},
        ),
        migrations.AddField(model_name="payment", name="gross_amount", field=models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True)),
        migrations.AddField(model_name="payment", name="platform_fee_amount", field=models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=10)),
        migrations.AddField(model_name="payment", name="teacher_amount", field=models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=10)),
        migrations.AddField(model_name="payment", name="stripe_charge_id", field=models.CharField(blank=True, default="", max_length=255)),
        migrations.AddField(model_name="payment", name="teacher", field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="course_payments", to="users.teacherprofile")),
    ]
