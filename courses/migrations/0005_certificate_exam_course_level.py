from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("courses", "0004_course_course_provider"),
    ]

    operations = [
        migrations.AddField(
            model_name="assessment",
            name="assessment_payload",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="assessment",
            name="assessment_type",
            field=models.CharField(
                choices=[("multiple", "Multiple Choice"), ("true_false", "True/False"), ("matching", "Matching")],
                default="multiple",
                max_length=30,
            ),
        ),
        migrations.AddField(
            model_name="assessment",
            name="course",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="certificate_exams",
                to="courses.course",
            ),
        ),
        migrations.AlterField(
            model_name="assessment",
            name="title",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.RemoveField(
            model_name="assessment",
            name="module",
        ),
    ]
