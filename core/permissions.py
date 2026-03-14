from rest_framework import permissions


class RolePermission(permissions.BasePermission):
    allowed_roles: list[str] = []

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if hasattr(view, "allowed_roles"):
            allowed_roles = view.allowed_roles
        else:
            allowed_roles = self.allowed_roles
        return not allowed_roles or user.role in allowed_roles


class IsAuthenticatedAndPasswordValid(permissions.IsAuthenticated):
    """Blocks access when a user still needs to change the default password."""

    def has_permission(self, request, view):
        base = super().has_permission(request, view)
        if not base:
            return False
        user = request.user
        bypass = getattr(view, "allow_password_change_bypass", False)
        if getattr(user, "must_change_password", False) and not bypass:
            return False
        return True


class IsSuperAdmin(RolePermission):
    allowed_roles = ["super_admin"]


class IsOrgAdmin(RolePermission):
    allowed_roles = ["org_admin"]


class IsCourseProvider(RolePermission):
    allowed_roles = ["course_provider", "super_admin"]


class IsMember(RolePermission):
    allowed_roles = ["member", "org_admin", "super_admin", "course_provider"]