from django.contrib.auth import get_user_model
from rest_framework import serializers

from .models import Alert, AlertDelivery, AlertView

User = get_user_model()


class AlertSerializer(serializers.ModelSerializer):
    total_deliveries = serializers.IntegerField(read_only=True)
    sent_deliveries = serializers.IntegerField(read_only=True)
    failed_deliveries = serializers.IntegerField(read_only=True)
    views_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Alert
        fields = [
            "id",
            "title",
            "message",
            "severity",
            "status",
            "notify_email",
            "notify_sms",
            "organization",
            "created_by",
            "published_at",
            "created_at",
            "updated_at",
            "total_deliveries",
            "sent_deliveries",
            "failed_deliveries",
            "views_count",
        ]
        read_only_fields = [
            "id",
            "created_by",
            "published_at",
            "created_at",
            "updated_at",
            "total_deliveries",
            "sent_deliveries",
            "failed_deliveries",
            "views_count",
        ]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["total_deliveries"] = instance.deliveries.count()
        data["sent_deliveries"] = instance.deliveries.filter(status=AlertDelivery.STATUS_SENT).count()
        data["failed_deliveries"] = instance.deliveries.filter(status=AlertDelivery.STATUS_FAILED).count()
        data["views_count"] = instance.views.count()
        return data


class AlertDeliverySerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source="user.email", read_only=True)

    class Meta:
        model = AlertDelivery
        fields = [
            "id",
            "alert",
            "user",
            "user_email",
            "channel",
            "status",
            "detail",
            "delivered_at",
            "created_at",
        ]
        read_only_fields = ["id", "delivered_at", "created_at", "user_email"]


class AlertViewSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source="user.email", read_only=True)

    class Meta:
        model = AlertView
        fields = ["id", "alert", "user", "user_email", "viewed_at"]
        read_only_fields = ["id", "viewed_at", "user_email"]
