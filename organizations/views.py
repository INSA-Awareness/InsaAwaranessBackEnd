from django.utils import timezone
from rest_framework import viewsets, permissions, decorators, response, status

from core.mixins import OrgScopedViewSetMixin
from core.permissions import IsSuperAdmin, IsOrgAdmin
from .models import Organization, OrganizationMembership, OrganizationApplication
from .serializers import OrganizationSerializer, OrganizationMembershipSerializer, OrganizationApplicationSerializer


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


class OrganizationApplicationViewSet(viewsets.ModelViewSet):
    queryset = OrganizationApplication.objects.all()
    serializer_class = OrganizationApplicationSerializer
    permission_classes = [permissions.AllowAny]
    filterset_fields = ["status", "name", "contact_email"]
    search_fields = ["name", "contact_email", "contact_phone", "address"]

    def get_permissions(self):
        if self.action in ["list", "retrieve", "approve", "reject"]:
            return [IsSuperAdmin()]
        if self.action in ["create"]:
            return [permissions.AllowAny()]
        return super().get_permissions()

    def perform_create(self, serializer):
        user = self.request.user if self.request.user.is_authenticated else None
        serializer.save(submitted_by=user, status=OrganizationApplication.STATUS_PENDING)

    def _approve_application(self, application, reviewer):
        if application.status == OrganizationApplication.STATUS_APPROVED:
            return False
        application.status = OrganizationApplication.STATUS_APPROVED
        application.reviewed_by = reviewer
        application.reviewed_at = timezone.now()
        application.save()
        # Create organization if not exists with same name
        org, _ = Organization.objects.get_or_create(
            name=application.name,
            defaults={
                "description": application.description,
                "created_by": reviewer,
            },
        )
        return org

    @decorators.action(detail=True, methods=["post"], permission_classes=[IsSuperAdmin])
    def approve(self, request, pk=None):
        application = self.get_object()
        org = self._approve_application(application, request.user)
        return response.Response(
            {
                "detail": "Application approved",
                "organization_id": str(org.id) if org else None,
            }
        )

    @decorators.action(detail=True, methods=["post"], permission_classes=[IsSuperAdmin])
    def reject(self, request, pk=None):
        application = self.get_object()
        if application.status == OrganizationApplication.STATUS_REJECTED:
            return response.Response({"detail": "Already rejected"}, status=status.HTTP_200_OK)
        application.status = OrganizationApplication.STATUS_REJECTED
        application.reviewed_by = request.user
        application.reviewed_at = timezone.now()
        application.save()
        return response.Response({"detail": "Application rejected"})


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