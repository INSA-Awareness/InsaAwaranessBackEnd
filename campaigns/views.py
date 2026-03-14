from rest_framework import viewsets, permissions

from core.permissions import IsSuperAdmin
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
            return [IsSuperAdmin()]
        return super().get_permissions()