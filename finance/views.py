from rest_framework import viewsets, permissions, decorators, response

from core.mixins import OrgScopedViewSetMixin
from core.permissions import IsSuperAdmin, IsOrgAdmin
from .models import PaymentApproval
from .serializers import PaymentApprovalSerializer


class PaymentApprovalViewSet(OrgScopedViewSetMixin, viewsets.ModelViewSet):
    queryset = PaymentApproval.objects.select_related("organization", "reviewed_by", "created_by")
    serializer_class = PaymentApprovalSerializer
    permission_classes = [permissions.IsAuthenticated]
    organization_field = "organization"

    def get_permissions(self):
        if self.action in ["create"]:
            return [IsOrgAdmin()]
        if self.action in ["approve", "reject", "update", "partial_update", "destroy"]:
            return [IsSuperAdmin()]
        return super().get_permissions()

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user, status=PaymentApproval.STATUS_PENDING)

    @decorators.action(detail=True, methods=["post"], permission_classes=[IsSuperAdmin])
    def approve(self, request, pk=None):
        approval = self.get_object()
        approval.status = PaymentApproval.STATUS_APPROVED
        approval.reviewed_by = request.user
        approval.save()
        return response.Response({"detail": "Approved"})

    @decorators.action(detail=True, methods=["post"], permission_classes=[IsSuperAdmin])
    def reject(self, request, pk=None):
        approval = self.get_object()
        approval.status = PaymentApproval.STATUS_REJECTED
        approval.reviewed_by = request.user
        approval.save()
        return response.Response({"detail": "Rejected"})