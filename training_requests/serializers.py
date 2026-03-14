from rest_framework import serializers

from .models import TrainingRequest


class TrainingRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = TrainingRequest
        fields = [
            "id",
            "organization",
            "created_by",
            "description",
            "attachment_url",
            "status",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_by", "status", "created_at", "updated_at"]