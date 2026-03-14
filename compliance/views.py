from rest_framework import viewsets, permissions

from core.mixins import OrgScopedViewSetMixin
from core.permissions import IsSuperAdmin, IsOrgAdmin
from .models import ComplianceReport
from .serializers import ComplianceReportSerializer


class ComplianceReportViewSet(OrgScopedViewSetMixin, viewsets.ModelViewSet):
    queryset = ComplianceReport.objects.select_related("organization", "created_by")
    serializer_class = ComplianceReportSerializer
    permission_classes = [permissions.IsAuthenticated]
    organization_field = "organization"

    def get_permissions(self):
        if self.action in ["create", "update", "partial_update", "destroy"]:
            return [IsOrgAdmin()]
        return super().get_permissions()

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    def get_queryset(self):
        qs = super().get_queryset()
        if self.request.user.role == "super_admin":
            return qs
        return qs.filter(organization__in=self.request.user.memberships.values_list("organization_id", flat=True))