from rest_framework import viewsets, permissions, decorators, response

from core.mixins import OrgScopedViewSetMixin
from core.permissions import IsCourseProvider, IsSuperAdmin
from .models import Resource
from .serializers import ResourceSerializer


class ResourceViewSet(OrgScopedViewSetMixin, viewsets.ModelViewSet):
    queryset = Resource.objects.select_related("organization", "created_by")
    serializer_class = ResourceSerializer
    permission_classes = [permissions.IsAuthenticated]
    organization_field = "organization"

    def get_permissions(self):
        if self.action in ["create", "update", "partial_update", "destroy", "publish"]:
            return [IsCourseProvider()]
        return super().get_permissions()

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @decorators.action(detail=True, methods=["post"], permission_classes=[IsSuperAdmin])
    def publish(self, request, pk=None):
        resource = self.get_object()
        resource.status = Resource.STATUS_PUBLISHED
        resource.save()
        return response.Response({"detail": "Published"})