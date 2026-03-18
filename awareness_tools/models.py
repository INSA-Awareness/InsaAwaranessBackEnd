import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone

from core.models import SoftDeleteModel

User = settings.AUTH_USER_MODEL


class AwarenessTool(SoftDeleteModel):
    STATUS_ENABLED = "enabled"
    STATUS_DISABLED = "disabled"
    STATUS_CHOICES = [
        (STATUS_ENABLED, "Enabled"),
        (STATUS_DISABLED, "Disabled"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_ENABLED)
    config = models.JSONField(default=dict, blank=True)
    created_by = models.ForeignKey(User, related_name="awareness_tools_created", on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    @property
    def is_enabled(self) -> bool:
        return self.status == self.STATUS_ENABLED

    def toggle_status(self):
        self.status = self.STATUS_ENABLED if self.status == self.STATUS_DISABLED else self.STATUS_DISABLED
        self.save(update_fields=["status", "updated_at"])


class AwarenessToolUsage(models.Model):
    ACTION_USE = "use"
    ACTION_CONFIGURE = "configure"
    ACTION_VIEW = "view"
    ACTION_CHOICES = [
        (ACTION_USE, "Use"),
        (ACTION_CONFIGURE, "Configure"),
        (ACTION_VIEW, "View"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tool = models.ForeignKey(AwarenessTool, related_name="usages", on_delete=models.CASCADE)
    user = models.ForeignKey(User, related_name="awareness_tool_usages", on_delete=models.SET_NULL, null=True, blank=True)
    action = models.CharField(max_length=32, choices=ACTION_CHOICES, default=ACTION_USE)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    @staticmethod
    def log(tool: "AwarenessTool", user=None, action: str = ACTION_USE, metadata: dict | None = None):
        return AwarenessToolUsage.objects.create(tool=tool, user=user, action=action, metadata=metadata or {})
