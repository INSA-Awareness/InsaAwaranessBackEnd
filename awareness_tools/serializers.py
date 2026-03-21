from rest_framework import serializers

from .models import AwarenessTool, AwarenessToolUsage


class AwarenessToolSerializer(serializers.ModelSerializer):
    usage_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = AwarenessTool
        fields = [
            "id",
            "name",
            "description",
            "status",
            "config",
            "created_by",
            "created_at",
            "updated_at",
            "usage_count",
        ]
        read_only_fields = ["id", "created_by", "created_at", "updated_at", "usage_count"]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["usage_count"] = instance.usages.count()
        return data


class PublicAwarenessToolSerializer(serializers.ModelSerializer):
    class Meta:
        model = AwarenessTool
        fields = ["id", "name", "description", "status", "created_at", "updated_at"]
        read_only_fields = fields


class AwarenessToolConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = AwarenessTool
        fields = ["config"]


class AwarenessToolUsageSerializer(serializers.ModelSerializer):
    tool_name = serializers.CharField(source="tool.name", read_only=True)
    user_email = serializers.EmailField(source="user.email", read_only=True)

    class Meta:
        model = AwarenessToolUsage
        fields = ["id", "tool", "tool_name", "user", "user_email", "action", "metadata", "created_at"]
        read_only_fields = ["id", "tool_name", "user_email", "created_at"]
