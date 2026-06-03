import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0014_lesson_fields'),
    ]

    operations = [
        migrations.CreateModel(
            name='Test',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=255)),
                ('description', models.TextField(blank=True, default='')),
                ('passing_score', models.PositiveSmallIntegerField(default=3)),
                ('order', models.PositiveSmallIntegerField()),
                ('is_deleted', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('module', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='tests', to='courses.module')),
            ],
            options={
                'db_table': 'tests',
                'ordering': ['order'],
            },
        ),
        migrations.CreateModel(
            name='Question',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('question_type', models.CharField(
                    choices=[
                        ('multiple_choice', 'Multiple Choice'),
                        ('true_false', 'True/False'),
                        ('short_answer', 'Short Answer'),
                    ],
                    default='multiple_choice',
                    max_length=20,
                )),
                ('text', models.TextField()),
                ('options', models.JSONField(blank=True, default=list)),
                ('correct_index', models.SmallIntegerField(blank=True, null=True)),
                ('correct_bool', models.BooleanField(blank=True, null=True)),
                ('sample_answer', models.TextField(blank=True, default='')),
                ('order', models.PositiveSmallIntegerField()),
                ('is_deleted', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('test', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='questions', to='courses.test')),
            ],
            options={
                'db_table': 'questions',
                'ordering': ['order'],
            },
        ),
        migrations.AddConstraint(
            model_name='test',
            constraint=models.UniqueConstraint(
                condition=models.Q(('is_deleted', False)),
                fields=('module', 'order'),
                name='unique_active_test_order_per_module',
            ),
        ),
    ]
