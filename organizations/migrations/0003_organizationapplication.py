import uuid

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("organizations", "0002_organization_deleted_at_organization_is_deleted_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="OrganizationApplication",
            fields=[
                ("deleted_at", models.DateTimeField(blank=True, null=True)),
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("name", models.CharField(max_length=255)),
                ("description", models.TextField()),
                ("contact_email", models.EmailField(max_length=254)),
                ("contact_phone", models.CharField(max_length=64)),
                ("website", models.URLField(blank=True)),
                ("address", models.CharField(max_length=255)),
                (
                    "status",
                    models.CharField(
                        choices=[("pending", "Pending"), ("approved", "Approved"), ("rejected", "Rejected")],
                        default="pending",
                        max_length=20,
                    ),
                ),
                ("reviewed_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "reviewed_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="org_applications_reviewed",
                        to="accounts.user",
                    ),
                ),
                (
                    "submitted_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="org_applications",
                        to="accounts.user",
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
                "unique_together": {("name", "contact_email")},
            },
        ),
    ]
