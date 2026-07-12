class OrgScopedViewSetMixin:
    organization_field = "organization"

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if not user.is_authenticated:
            return qs.none()
        if getattr(user, "role", None) == "super_admin":
            return qs
        org_ids = user.memberships.values_list("organization_id", flat=True)
        return qs.filter(**{f"{self.organization_field}__in": org_ids})

    def perform_create(self, serializer):
        user = self.request.user
        organization = None
        if getattr(user, "role", None) != "super_admin":
            organization = user.primary_organization
        save_kwargs = {}
        if "created_by" in serializer.fields:
            save_kwargs["created_by"] = user
        if self.organization_field in serializer.fields:
            save_kwargs[self.organization_field] = organization
        serializer.save(**save_kwargs)