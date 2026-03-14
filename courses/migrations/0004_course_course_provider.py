from django.db import migrations, models
from django.conf import settings


def set_course_provider(apps, schema_editor):
    Course = apps.get_model("courses", "Course")
    User = apps.get_model("accounts", "User")

    fallback = User.objects.filter(role="course_provider").first()
    if not fallback:
        fallback = User.objects.filter(role="super_admin").first()

    missing = []
    for course in Course.objects.all():
        if course.course_provider_id:
            continue
        if course.created_by_id:
            course.course_provider_id = course.created_by_id
        elif fallback:
            course.course_provider = fallback
        else:
            missing.append(str(course.id))
            continue
        course.save(update_fields=["course_provider"])

    if missing:
        raise RuntimeError(
            "Cannot finalize course_provider migration; provide a course provider for courses: "
            + ",".join(missing)
        )


def unset_course_provider(apps, schema_editor):
    # No-op rollback
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("courses", "0003_enrollmentprofilesnapshot"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="course",
            name="course_provider",
            field=models.ForeignKey(
                related_name="courses_provided",
                null=True,
                on_delete=models.PROTECT,
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.RunPython(set_course_provider, unset_course_provider),
        migrations.AlterField(
            model_name="course",
            name="course_provider",
            field=models.ForeignKey(
                related_name="courses_provided",
                on_delete=models.PROTECT,
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
