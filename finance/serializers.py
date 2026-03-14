from rest_framework import serializers

from .models import PaymentApproval


class PaymentApprovalSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentApproval
        fields = [
            "id",
            "organization",
            "amount",
            "status",
            "reviewed_by",
            "created_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "status", "reviewed_by", "created_by", "created_at", "updated_at"]