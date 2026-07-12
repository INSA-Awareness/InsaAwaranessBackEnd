from rest_framework import viewsets

from core.permissions import IsSuperAdmin
from .models import AuditLog
from .serializers import AuditLogSerializer


class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = AuditLog.objects.select_related("actor").all()
    serializer_class = AuditLogSerializer
    permission_classes = [IsSuperAdmin]
    filterset_fields = ["action", "app_label", "model", "actor"]
    search_fields = ["model", "object_id", "actor__email"]
    ordering_fields = ["created_at"]
    ordering = ["-created_at"]
