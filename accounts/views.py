from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.utils.translation import gettext_lazy as _
from rest_framework import generics, permissions, viewsets, decorators, response, status
from rest_framework_simplejwt.views import TokenObtainPairView

from core.permissions import IsSuperAdmin, IsOrgAdmin
from .serializers import (
    RegisterSerializer,
    UserSerializer,
    ChangePasswordSerializer,
    PasswordResetRequestSerializer,
    PasswordResetConfirmSerializer,
    AdminCreateUserSerializer,
    OrgAdminCreateUserSerializer,
    CustomTokenObtainPairSerializer,
    BackgroundProfileSerializer,
)
from .models import BackgroundProfile
from drf_spectacular.utils import extend_schema, OpenApiExample

User = get_user_model()


class LoginView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer
    permission_classes = [permissions.AllowAny]
    allow_password_change_bypass = True


class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]
    allow_password_change_bypass = True


class MeView(generics.RetrieveAPIView):
    serializer_class = UserSerializer
    allow_password_change_bypass = True

    def get_object(self):
        return self.request.user


class ChangePasswordView(generics.UpdateAPIView):
    serializer_class = ChangePasswordSerializer
    allow_password_change_bypass = True

    def get_object(self):
        return self.request.user

    def update(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return response.Response({"detail": "Password updated"})


class BackgroundProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = BackgroundProfileSerializer

    def get_object(self):
        profile, _ = BackgroundProfile.objects.get_or_create(user=self.request.user)
        return profile


class PasswordResetRequestView(generics.GenericAPIView):
    serializer_class = PasswordResetRequestSerializer
    permission_classes = [permissions.AllowAny]
    allow_password_change_bypass = True

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = serializer.save()
        send_mail(
            subject="Password reset instructions",
            message=f"Use token {payload['token']} with uid {payload['uid']} to reset your password.",
            from_email=None,
            recipient_list=[serializer.validated_data["email"]],
            fail_silently=True,
        )
        return response.Response({"detail": "Reset token generated", **payload})


class PasswordResetConfirmView(generics.GenericAPIView):
    serializer_class = PasswordResetConfirmSerializer
    permission_classes = [permissions.AllowAny]
    allow_password_change_bypass = True

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return response.Response({"detail": "Password reset successful"})


class UserAdminViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsSuperAdmin]

    def get_serializer_class(self):
        if getattr(self, "action", None) == "create_org_admin":
            return OrgAdminCreateUserSerializer
        if getattr(self, "action", None) in {
            "create_course_provider",
            "create_member",
            "create_super_admin",
        }:
            return AdminCreateUserSerializer
        return super().get_serializer_class()

    def get_permissions(self):
        user = getattr(self, "request", None) and getattr(self.request, "user", None)
        if not user or not getattr(user, "is_authenticated", False):
            return super().get_permissions()
        if self.action in ["create_member", "list", "retrieve"]:
            if user.role == User.ROLE_ORG_ADMIN:
                return [IsOrgAdmin()]
        if self.action in ["create_course_provider", "create_org_admin", "create_super_admin"]:
            return [IsSuperAdmin()]
        return super().get_permissions()

    def get_queryset(self):
        qs = super().get_queryset()
        user = getattr(self, "request", None) and getattr(self.request, "user", None)
        if self.action in ["list", "retrieve"] and user and getattr(user, "is_authenticated", False) and user.role == User.ROLE_ORG_ADMIN:
            org_ids = self.request.user.memberships.values_list("organization_id", flat=True)
            return qs.filter(memberships__organization_id__in=org_ids).distinct()
        return qs

    def create(self, request, *args, **kwargs):
        return response.Response(
            {"detail": "Use role-specific endpoints to create users."},
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    def _create_user(self, request, role, serializer_cls=AdminCreateUserSerializer):
        if request.user.role == User.ROLE_ORG_ADMIN and role != User.ROLE_MEMBER:
            raise PermissionDenied("Org admin can only create organization members")
        if request.user.role == User.ROLE_SUPER_ADMIN and role == User.ROLE_MEMBER:
            raise PermissionDenied("Super admin cannot create organization members")

        serializer = serializer_cls(
            data=request.data, context={"request": request, "role": role}
        )
        serializer.is_valid(raise_exception=True)
        user, generated_password = serializer.save()
        send_mail(
            subject=_("Your account is ready"),
            message=_("Login with the provided email and password: %(password)s")
            % {"password": generated_password},
            from_email=None,
            recipient_list=[user.email],
            fail_silently=True,
        )
        payload = {
            "user": UserSerializer(user).data,
            "must_change_password": True,
        }
        from django.conf import settings

        if settings.DEBUG:
            payload["temporary_password"] = generated_password
        return response.Response(payload, status=status.HTTP_201_CREATED)

    @decorators.action(detail=False, methods=["post"], url_path="org-admins")
    @extend_schema(
        request=OrgAdminCreateUserSerializer,
        responses=UserSerializer,
        examples=[
            OpenApiExample(
                "Create org admin",
                value={
                    "email": "admin@example.com",
                    "first_name": "John",
                    "last_name": "Doe",
                    "preferred_language": "en",
                    "organization_id": "11111111-2222-3333-4444-555555555555",
                },
            )
        ],
    )
    def create_org_admin(self, request):
        return self._create_user(request, User.ROLE_ORG_ADMIN, serializer_cls=OrgAdminCreateUserSerializer)

    @decorators.action(detail=False, methods=["post"], url_path="course-providers")
    @extend_schema(request=AdminCreateUserSerializer, responses=UserSerializer)
    def create_course_provider(self, request):
        return self._create_user(request, User.ROLE_COURSE_PROVIDER)

    @decorators.action(detail=False, methods=["post"], url_path="members")
    @extend_schema(request=AdminCreateUserSerializer, responses=UserSerializer)
    def create_member(self, request):
        return self._create_user(request, User.ROLE_MEMBER)

    @decorators.action(detail=False, methods=["post"], url_path="super-admins")
    @extend_schema(request=AdminCreateUserSerializer, responses=UserSerializer)
    def create_super_admin(self, request):
        return self._create_user(request, User.ROLE_SUPER_ADMIN)