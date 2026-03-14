from rest_framework import viewsets, permissions, decorators, response

from core.mixins import OrgScopedViewSetMixin
from core.permissions import IsSuperAdmin, IsOrgAdmin, IsMember
from .models import TrainingRequest
from .serializers import TrainingRequestSerializer


class TrainingRequestViewSet(OrgScopedViewSetMixin, viewsets.ModelViewSet):
    queryset = TrainingRequest.objects.select_related("organization", "created_by")
    serializer_class = TrainingRequestSerializer
    permission_classes = [permissions.IsAuthenticated]
    organization_field = "organization"

    def get_permissions(self):
        if self.action in ["create"]:
            return [IsMember()]
        if self.action in ["update", "partial_update", "destroy", "approve", "reject"]:
            return [IsSuperAdmin()]
        return super().get_permissions()

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user, status=TrainingRequest.STATUS_PENDING)

    @decorators.action(detail=True, methods=["post"], permission_classes=[IsSuperAdmin])
    def approve(self, request, pk=None):
        training = self.get_object()
        training.status = TrainingRequest.STATUS_APPROVED
        training.save()
        return response.Response({"detail": "Approved"})

    @decorators.action(detail=True, methods=["post"], permission_classes=[IsSuperAdmin])
    def reject(self, request, pk=None):
        training = self.get_object()
        training.status = TrainingRequest.STATUS_REJECTED
        training.save()
        return response.Response({"detail": "Rejected"})