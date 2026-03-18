from rest_framework import viewsets, permissions

from core.permissions import IsSuperAdminOrOrgAdmin
from core.mixins import OrgScopedViewSetMixin
from .models import Campaign
from .serializers import CampaignSerializer


class CampaignViewSet(OrgScopedViewSetMixin, viewsets.ModelViewSet):
    queryset = Campaign.objects.select_related("organization", "created_by")
    serializer_class = CampaignSerializer
    permission_classes = [permissions.IsAuthenticated]
    organization_field = "organization"

    def get_permissions(self):
        if self.action in ["create", "update", "partial_update", "destroy"]:
            return [IsSuperAdminOrOrgAdmin()]
        return super().get_permissions()

    def perform_create(self, serializer):
        user = self.request.user
        organization = None
        if getattr(user, "role", None) == "super_admin":
            organization = serializer.validated_data.get("organization")
        else:
            organization = getattr(user, "primary_organization", None)
        serializer.save(created_by=user, organization=organization)