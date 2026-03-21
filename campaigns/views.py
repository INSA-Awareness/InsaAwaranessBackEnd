from rest_framework import viewsets, permissions

from core.permissions import IsSuperAdminOrOrgAdmin
from .models import Campaign
from .serializers import CampaignSerializer


class CampaignViewSet(viewsets.ModelViewSet):
    queryset = Campaign.objects.select_related("organization", "created_by")
    serializer_class = CampaignSerializer
    permission_classes = [permissions.AllowAny]

    def get_permissions(self):
        if self.action in ["create", "update", "partial_update", "destroy"]:
            return [IsSuperAdminOrOrgAdmin()]
        if self.action in ["list", "retrieve"]:
            return [permissions.AllowAny()]
        return super().get_permissions()

    def get_queryset(self):
        qs = super().get_queryset()
        user = getattr(self.request, "user", None)
        if not user or not getattr(user, "is_authenticated", False):
            return qs.filter(status=Campaign.STATUS_LIVE)
        if getattr(user, "role", None) == "super_admin":
            return qs
        org_ids = user.memberships.values_list("organization_id", flat=True)
        return qs.filter(organization_id__in=org_ids)

    def perform_create(self, serializer):
        user = self.request.user
        organization = None
        if getattr(user, "role", None) == "super_admin":
            organization = serializer.validated_data.get("organization")
        else:
            organization = getattr(user, "primary_organization", None)
        serializer.save(created_by=user, organization=organization)