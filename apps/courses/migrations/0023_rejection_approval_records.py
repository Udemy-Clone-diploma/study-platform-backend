from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("courses", "0022_moderation_review_course_status"),
        ("users", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="RejectedCourseRecord",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("course", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="rejection_records", to="courses.course")),
                ("teacher_profile", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="course_rejection_records", to="users.teacherprofile")),
                ("moderator_profile", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="course_rejection_records", to="users.moderatorprofile")),
                ("course_slug", models.CharField(max_length=255)),
                ("course_title", models.CharField(max_length=255)),
                ("course_image_url", models.TextField(blank=True, null=True)),
                ("course_category", models.CharField(blank=True, default="", max_length=255)),
                ("course_level", models.CharField(blank=True, default="", max_length=20)),
                ("basics_field_statuses", models.JSONField(blank=True, default=dict)),
                ("basics_action", models.CharField(blank=True, default="", max_length=20)),
                ("basics_comment", models.TextField(blank=True, default="")),
                ("content_item_statuses", models.JSONField(blank=True, default=dict)),
                ("content_action", models.CharField(blank=True, default="", max_length=20)),
                ("content_comment", models.TextField(blank=True, default="")),
                ("final_action", models.CharField(blank=True, default="", max_length=20)),
                ("final_comment", models.TextField(blank=True, default="")),
                ("changed_fields", models.JSONField(blank=True, default=list)),
                ("rejected_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={"db_table": "course_rejection_records", "ordering": ["-rejected_at"]},
        ),
        migrations.CreateModel(
            name="ApprovedCourseRecord",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("course", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="approval_records", to="courses.course")),
                ("teacher_profile", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="course_approval_records", to="users.teacherprofile")),
                ("moderator_profile", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="course_approval_records", to="users.moderatorprofile")),
                ("course_slug", models.CharField(max_length=255)),
                ("course_title", models.CharField(max_length=255)),
                ("course_image_url", models.TextField(blank=True, null=True)),
                ("course_category", models.CharField(blank=True, default="", max_length=255)),
                ("course_level", models.CharField(blank=True, default="", max_length=20)),
                ("changed_fields", models.JSONField(blank=True, default=list)),
                ("approved_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={"db_table": "course_approval_records", "ordering": ["-approved_at"]},
        ),
    ]
