from django.db.models import Q
from rest_framework import viewsets, permissions, decorators, response

from core.permissions import IsCourseProvider, IsSuperAdmin
from .models import Resource
from .serializers import ResourceSerializer


class ResourceViewSet(viewsets.ModelViewSet):
    queryset = Resource.objects.select_related("organization", "created_by")
    serializer_class = ResourceSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_permissions(self):
        if self.action in ["create", "update", "partial_update", "destroy", "publish"]:
            # Course providers already include super_admin in allowed roles
            return [IsCourseProvider()]
        if self.action in ["list", "retrieve"]:
            return [permissions.AllowAny()]
        return super().get_permissions()

    def get_queryset(self):
        qs = super().get_queryset()
        audience = self.request.query_params.get("audience")
        if audience:
            qs = qs.filter(audience=audience)

        user = self.request.user
        if not user.is_authenticated:
            return qs.filter(status=Resource.STATUS_PUBLISHED)

        if getattr(user, "role", None) == "super_admin":
            return qs

        org_ids = user.memberships.values_list("organization_id", flat=True)
        return qs.filter(
            Q(status=Resource.STATUS_PUBLISHED)
            | Q(organization_id__in=org_ids)
            | Q(created_by=user)
        )

    def perform_create(self, serializer):
        user = self.request.user
        organization = None if getattr(user, "role", None) == "super_admin" else user.primary_organization
        serializer.save(created_by=user, organization=organization)

    @decorators.action(detail=True, methods=["post"], permission_classes=[IsSuperAdmin])
    def publish(self, request, pk=None):
        resource = self.get_object()
        resource.status = Resource.STATUS_PUBLISHED
        resource.save()
        return response.Response({"detail": "Published"})