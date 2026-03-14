from rest_framework import serializers

from .models import ComplianceReport


class ComplianceReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = ComplianceReport
        fields = [
            "id",
            "organization",
            "title",
            "status",
            "report_data",
            "created_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_by", "created_at", "updated_at"]