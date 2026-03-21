from django.db.models import Count
from rest_framework import viewsets, permissions, decorators, response, status, filters

from core.permissions import IsSuperAdmin
from .models import AwarenessTool, AwarenessToolUsage
from .serializers import (
    AwarenessToolSerializer,
    AwarenessToolConfigSerializer,
    AwarenessToolUsageSerializer,
    PublicAwarenessToolSerializer,
)


class AwarenessToolViewSet(viewsets.ModelViewSet):
    queryset = AwarenessTool.objects.all().prefetch_related("usages")
    serializer_class = AwarenessToolSerializer
    permission_classes = [IsSuperAdmin]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["name", "description"]
    ordering_fields = ["name", "created_at", "updated_at"]
    ordering = ["name"]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @decorators.action(detail=True, methods=["patch"], url_path="toggle-status")
    def toggle_status(self, request, pk=None):
        tool = self.get_object()
        tool.toggle_status()
        return response.Response({"status": tool.status})

    @decorators.action(detail=True, methods=["post"], url_path="configure")
    def configure(self, request, pk=None):
        tool = self.get_object()
        serializer = AwarenessToolConfigSerializer(tool, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        AwarenessToolUsage.log(tool, user=request.user, action=AwarenessToolUsage.ACTION_CONFIGURE, metadata=request.data)
        return response.Response(serializer.data)

    @decorators.action(detail=False, methods=["get"], url_path="usage-stats")
    def usage_stats(self, request):
        total_tools = AwarenessTool.objects.count()
        enabled_tools = AwarenessTool.objects.filter(status=AwarenessTool.STATUS_ENABLED).count()
        disabled_tools = AwarenessTool.objects.filter(status=AwarenessTool.STATUS_DISABLED).count()
        total_usage = AwarenessToolUsage.objects.count()
        usage_by_tool = (
            AwarenessToolUsage.objects.values("tool_id", "tool__name")
            .annotate(count=Count("id"))
            .order_by("tool__name")
        )
        return response.Response(
            {
                "total_tools": total_tools,
                "enabled_tools": enabled_tools,
                "disabled_tools": disabled_tools,
                "total_usage": total_usage,
                "usage_by_tool": list(usage_by_tool),
            }
        )

    @decorators.action(detail=True, methods=["get"], url_path="usage")
    def usage(self, request, pk=None):
        tool = self.get_object()
        qs = tool.usages.values("action").annotate(count=Count("id")).order_by("action")
        return response.Response({"tool_id": str(tool.id), "usage": list(qs)})


class AwarenessToolUsageViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = AwarenessToolUsage.objects.select_related("tool", "user")
    serializer_class = AwarenessToolUsageSerializer
    permission_classes = [IsSuperAdmin]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["tool__name", "user__email", "action"]
    ordering_fields = ["created_at"]
    ordering = ["-created_at"]


class PublicAwarenessToolViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = AwarenessTool.objects.filter(status=AwarenessTool.STATUS_ENABLED).order_by("name")
    serializer_class = PublicAwarenessToolSerializer
    permission_classes = [permissions.AllowAny]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["name", "description"]
    ordering_fields = ["name", "created_at", "updated_at"]
    ordering = ["name"]
