from django.db import migrations, models
import django.db.models.deletion


def forward_migrate_pricing_plans(apps, schema_editor):
    """Create a CourseDeliveryFormat for each existing PricingPlan and link them."""
    PricingPlan = apps.get_model("courses", "PricingPlan")
    CourseDeliveryFormat = apps.get_model("courses", "CourseDeliveryFormat")

    kind_to_format = {"group": "group", "individual": "individual"}

    for plan in PricingPlan.objects.all():
        fmt = CourseDeliveryFormat.objects.create(
            course_id=plan.course_id,
            format_type=kind_to_format.get(plan.kind, "group"),
        )
        PricingPlan.objects.filter(pk=plan.pk).update(delivery_format_id=fmt.pk)


def reverse_migrate_pricing_plans(apps, schema_editor):
    """Restore course_id and kind on PricingPlan from its delivery_format."""
    PricingPlan = apps.get_model("courses", "PricingPlan")

    format_to_kind = {"group": "group", "individual": "individual",
                      "self_paced": "group", "scheduled": "group"}

    for plan in PricingPlan.objects.select_related("delivery_format").all():
        if plan.delivery_format_id:
            PricingPlan.objects.filter(pk=plan.pk).update(
                course_id=plan.delivery_format.course_id,
                kind=format_to_kind.get(plan.delivery_format.format_type, "group"),
            )


class Migration(migrations.Migration):

    dependencies = [
        ("courses", "0024_duration_hours_auto"),
    ]

    operations = [
        # 1. Create the new delivery_formats table
        migrations.CreateModel(
            name="CourseDeliveryFormat",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False)),
                ("format_type", models.CharField(
                    choices=[
                        ("self_paced",  "Self-paced"),
                        ("scheduled",   "Scheduled"),
                        ("individual",  "Individual (1-on-1 with teacher)"),
                        ("group",       "Group (with teacher)"),
                    ],
                    max_length=20,
                )),
                ("start_type", models.CharField(
                    blank=True, null=True,
                    choices=[("date", "Specific start date"), ("manual", "Manual activation")],
                    max_length=10,
                )),
                ("course_start_date", models.DateField(blank=True, null=True)),
                ("access_duration_days", models.PositiveIntegerField(blank=True, null=True)),
                ("start_date", models.DateField(blank=True, null=True)),
                ("enrollment_deadline", models.DateField(blank=True, null=True)),
                ("unlock_mode", models.CharField(
                    blank=True, null=True,
                    choices=[
                        ("immediate",  "All content unlocked immediately"),
                        ("date_based", "Unlock by date from course start"),
                        ("sequential", "Unlock after completing previous lesson"),
                    ],
                    max_length=20,
                )),
                ("max_students", models.PositiveSmallIntegerField(blank=True, null=True)),
                ("course", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="delivery_formats",
                    to="courses.course",
                )),
            ],
            options={"db_table": "course_delivery_formats", "ordering": ["format_type"]},
        ),
        migrations.AddConstraint(
            model_name="CourseDeliveryFormat",
            constraint=models.UniqueConstraint(
                fields=["course", "format_type"],
                name="unique_delivery_format_per_course",
            ),
        ),

        # 2. Add nullable delivery_format FK to PricingPlan
        migrations.AddField(
            model_name="PricingPlan",
            name="delivery_format",
            field=models.OneToOneField(
                null=True,
                blank=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="pricing",
                to="courses.coursedeliveryformat",
            ),
        ),

        # 3. Populate delivery_format for each existing PricingPlan
        migrations.RunPython(
            forward_migrate_pricing_plans,
            reverse_migrate_pricing_plans,
        ),

        # 4. Make delivery_format non-nullable
        migrations.AlterField(
            model_name="PricingPlan",
            name="delivery_format",
            field=models.OneToOneField(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="pricing",
                to="courses.coursedeliveryformat",
            ),
        ),

        # 5. Remove old unique constraint on PricingPlan
        migrations.RemoveConstraint(
            model_name="PricingPlan",
            name="unique_pricing_plan_per_kind",
        ),

        # 6. Remove old fields from PricingPlan
        migrations.RemoveField(model_name="PricingPlan", name="course"),
        migrations.RemoveField(model_name="PricingPlan", name="kind"),

        # 7. Add delivery_format FK (nullable) to Cohort
        migrations.AddField(
            model_name="Cohort",
            name="delivery_format",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="cohorts",
                to="courses.coursedeliveryformat",
            ),
        ),

        # 8. Add enrollment_deadline to Cohort
        migrations.AddField(
            model_name="Cohort",
            name="enrollment_deadline",
            field=models.DateField(blank=True, null=True),
        ),

        # 9. Remove delivery_mode from Cohort (replaced by delivery_format.format_type)
        migrations.RemoveField(model_name="Cohort", name="delivery_mode"),
    ]
