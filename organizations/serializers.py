from django.contrib.auth import get_user_model
from rest_framework import serializers

from .models import Organization, OrganizationMembership

User = get_user_model()


class OrganizationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = ["id", "name", "description", "created_by", "created_at"]
        read_only_fields = ["id", "created_by", "created_at"]


class OrganizationMembershipSerializer(serializers.ModelSerializer):
    user = serializers.PrimaryKeyRelatedField(queryset=User.objects.all())

    class Meta:
        model = OrganizationMembership
        fields = [
            "id",
            "user",
            "organization",
            "org_role",
            "department",
            "employee_id",
            "is_primary",
            "joined_at",
        ]
        read_only_fields = ["id", "joined_at"]

    def validate(self, attrs):
        request = self.context.get("request")
        if request and request.user.role == User.ROLE_ORG_ADMIN:
            org_ids = request.user.memberships.values_list("organization_id", flat=True)
            if attrs["organization"].id not in org_ids:
                raise serializers.ValidationError("You can only manage members within your organization")
        return attrs