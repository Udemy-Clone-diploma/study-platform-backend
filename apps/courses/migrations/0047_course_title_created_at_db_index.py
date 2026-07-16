from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("courses", "0046_category_featured_order"),
    ]

    operations = [
        migrations.AlterField(
            model_name="course",
            name="title",
            field=models.CharField(max_length=255, db_index=True),
        ),
        migrations.AlterField(
            model_name="course",
            name="created_at",
            field=models.DateTimeField(auto_now_add=True, db_index=True),
        ),
    ]
