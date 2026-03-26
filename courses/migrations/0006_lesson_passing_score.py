from django.db import migrations, models
import django.core.validators


class Migration(migrations.Migration):

    dependencies = [
        ("courses", "0005_certificate_exam_course_level"),
    ]

    operations = [
        migrations.AddField(
            model_name="lesson",
            name="passing_score",
            field=models.PositiveIntegerField(
                default=0,
                validators=[
                    django.core.validators.MinValueValidator(0),
                    django.core.validators.MaxValueValidator(100),
                ],
            ),
        ),
    ]
