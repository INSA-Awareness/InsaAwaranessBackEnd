from rest_framework import viewsets, permissions

from core.mixins import OrgScopedViewSetMixin
from core.permissions import IsSuperAdmin, IsOrgAdmin
from .models import Organization, OrganizationMembership
from .serializers import OrganizationSerializer, OrganizationMembershipSerializer


class OrganizationViewSet(viewsets.ModelViewSet):
    queryset = Organization.objects.all()
    serializer_class = OrganizationSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ["name"]
    search_fields = ["name", "description"]

    def get_permissions(self):
        if self.action in ["create", "update", "partial_update", "destroy"]:
            return [IsSuperAdmin()]
        return super().get_permissions()

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class OrganizationMembershipViewSet(OrgScopedViewSetMixin, viewsets.ModelViewSet):
    queryset = OrganizationMembership.objects.select_related("organization", "user")
    serializer_class = OrganizationMembershipSerializer
    permission_classes = [permissions.IsAuthenticated]
    organization_field = "organization"
    filterset_fields = ["organization", "org_role"]
    search_fields = ["user__email", "department", "employee_id"]

    def get_permissions(self):
        if self.action in ["create", "update", "partial_update", "destroy"]:
            return [IsOrgAdmin()]
        return super().get_permissions()