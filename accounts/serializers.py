import uuid

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
import re

User = get_user_model()
from .models import BackgroundProfile


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "first_name",
            "last_name",
            "role",
            "preferred_language",
            "is_active",
            "must_change_password",
        ]
        read_only_fields = ["id", "role", "is_active", "must_change_password"]


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "first_name",
            "last_name",
            "password",
            "preferred_language",
        ]
        read_only_fields = ["id"]

    def validate_password(self, value):
        validate_password(value)
        return value

    def create(self, validated_data):
        password = validated_data.pop("password")
        user = User.objects.create_user(role=User.ROLE_PUBLIC, **validated_data)
        user.set_password(password)
        user.must_change_password = False
        user.save()
        return user


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True)

    def validate_new_password(self, value):
        validate_password(value)
        return value

    def save(self, **kwargs):
        user = self.context["request"].user
        old_password = self.validated_data["old_password"]
        if not user.check_password(old_password):
            raise serializers.ValidationError({"old_password": "Incorrect password"})
        user.set_password(self.validated_data["new_password"])
        user.must_change_password = False
        user.save()
        return user


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate_email(self, value):
        if not User.objects.filter(email=value).exists():
            raise serializers.ValidationError("User with this email does not exist")
        return value

    def save(self, **kwargs):
        user = User.objects.get(email=self.validated_data["email"])
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        return {"uid": uid, "token": token}


class PasswordResetConfirmSerializer(serializers.Serializer):
    uid = serializers.CharField()
    token = serializers.CharField()
    new_password = serializers.CharField(write_only=True)

    def validate_new_password(self, value):
        validate_password(value)
        return value

    def save(self, **kwargs):
        from django.utils.http import urlsafe_base64_decode

        uid = urlsafe_base64_decode(self.validated_data["uid"]).decode()
        try:
            user = User.objects.get(pk=uid)
        except User.DoesNotExist:
            raise serializers.ValidationError("Invalid user reference")
        if not default_token_generator.check_token(user, self.validated_data["token"]):
            raise serializers.ValidationError("Invalid reset token")
        user.set_password(self.validated_data["new_password"])
        user.must_change_password = False
        user.save()
        return user


class AdminCreateUserSerializer(serializers.ModelSerializer):
    organization_id = serializers.UUIDField(required=False, allow_null=True)
    default_password = serializers.CharField(read_only=True)

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "first_name",
            "last_name",
            "role",
            "preferred_language",
            "organization_id",
            "default_password",
        ]
        read_only_fields = ["id", "default_password", "role"]

    def _resolve_organization(self, organization_id):
        from organizations.models import Organization

        try:
            return Organization.objects.get(pk=organization_id)
        except Organization.DoesNotExist:
            raise serializers.ValidationError({"organization_id": "Organization not found"})

    def validate(self, attrs):
        attrs = super().validate(attrs)
        request = self.context["request"]
        role = self.context["role"]
        organization_id = attrs.get("organization_id")

        if role == User.ROLE_ORG_ADMIN:
            if organization_id is None:
                raise serializers.ValidationError({"organization_id": "organization_id is required for organization admins"})
            attrs["organization_obj"] = self._resolve_organization(organization_id)
        elif role == User.ROLE_MEMBER:
            org = getattr(request.user, "primary_organization", None)
            if not org:
                raise serializers.ValidationError({"organization_id": "organization_id is required to create members"})
            attrs["organization_obj"] = org
        elif organization_id is not None:
            attrs["organization_obj"] = self._resolve_organization(organization_id)

        return attrs

    def create(self, validated_data):
        request = self.context["request"]
        role = self.context["role"]
        organization = validated_data.pop("organization_obj", None)
        validated_data.pop("organization_id", None)
        password = validated_data.pop("default_password", None) or uuid.uuid4().hex[:12]

        user = User.objects.create_user(role=role, **validated_data)
        user.set_password(password)
        user.must_change_password = True
        user.created_by = request.user
        user.save()

        if organization:
            from organizations.models import OrganizationMembership

            OrganizationMembership.objects.create(
                organization=organization,
                user=user,
                org_role=OrganizationMembership.ROLE_ADMIN if role == User.ROLE_ORG_ADMIN else OrganizationMembership.ROLE_MEMBER,
                is_primary=True,
            )

        return user, password


class OrgAdminCreateUserSerializer(AdminCreateUserSerializer):
    organization_id = serializers.UUIDField(required=True, allow_null=False)


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["role"] = user.role
        token["preferred_language"] = user.preferred_language
        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        user = self.user
        data.update(
            {
                "user": UserSerializer(user).data,
                "dashboard_route": user.dashboard_route,
                "must_change_password": user.must_change_password,
            }
        )
        return data


class BackgroundProfileSerializer(serializers.ModelSerializer):
    phone_number = serializers.CharField(required=True)

    class Meta:
        model = BackgroundProfile
        exclude = ["is_deleted", "deleted_at"]
        read_only_fields = ["id", "user"]

    def validate_phone_number(self, value):
        pattern = re.compile(r"^\+?[0-9]{7,15}$")
        if not pattern.match(value):
            raise serializers.ValidationError("Enter a valid phone number")
        return value

    def validate(self, attrs):
        nationality = attrs.get("nationality") or getattr(self.instance, "nationality", "")
        region = attrs.get("region") or getattr(self.instance, "region", "")
        employment_status = attrs.get("employment_status") or getattr(self.instance, "employment_status", "")
        unemployment_description = attrs.get("unemployment_description") or getattr(self.instance, "unemployment_description", "")
        is_information_confirmed = attrs.get("is_information_confirmed") if "is_information_confirmed" in attrs else getattr(self.instance, "is_information_confirmed", False)

        if nationality == BackgroundProfile.NATIONALITY_ETHIOPIA and not region:
            raise serializers.ValidationError({"region": "Region is required for Ethiopian nationality"})
        if employment_status in {"unemployed", "other"} and not unemployment_description:
            raise serializers.ValidationError({"unemployment_description": "Description is required when unemployed or other"})
        if not is_information_confirmed:
            raise serializers.ValidationError({"is_information_confirmed": "You must confirm the information"})
        return attrs