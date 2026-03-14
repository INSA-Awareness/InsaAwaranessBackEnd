from django.contrib.auth import get_user_model
from rest_framework import serializers

from organizations.models import Organization
from .models import Course, Module, Article, Video, Assessment, Enrollment, Certificate, Lesson

User = get_user_model()


class ArticleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Article
        fields = ["id", "module", "content", "order"]


class VideoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Video
        fields = ["id", "module", "video_url", "duration", "order"]


class AssessmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Assessment
        fields = ["id", "module", "title", "passing_score", "order"]


class ModuleSerializer(serializers.ModelSerializer):
    articles = ArticleSerializer(many=True, read_only=True)
    videos = VideoSerializer(many=True, read_only=True)
    assessments = AssessmentSerializer(many=True, read_only=True)
    lessons = serializers.SerializerMethodField()

    class Meta:
        model = Module
        fields = ["id", "course", "title", "order", "articles", "videos", "assessments", "lessons"]

    def get_lessons(self, obj):
        lessons = obj.lessons.order_by("order")
        return LessonSerializer(lessons, many=True).data


class CourseSerializer(serializers.ModelSerializer):
    created_by = serializers.PrimaryKeyRelatedField(read_only=True)
    course_provider = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(role=User.ROLE_COURSE_PROVIDER), required=False
    )
    organization = serializers.PrimaryKeyRelatedField(
        queryset=Organization.objects.all(), allow_null=True, required=False
    )

    class Meta:
        model = Course
        fields = [
            "id",
            "title",
            "description",
            "level",
            "organization",
            "course_provider",
            "created_by",
            "assigned_by",
            "status",
            "language",
            "is_active",
            "created_at",
        ]
        read_only_fields = ["id", "created_by", "assigned_by", "created_at"]

    def validate_course_provider(self, value):
        if value.role != User.ROLE_COURSE_PROVIDER:
            raise serializers.ValidationError("course_provider must have role=course_provider")
        return value

    def validate(self, attrs):
        attrs = super().validate(attrs)
        # Organization existence handled by PrimaryKeyRelatedField; no-op here
        return attrs


class CourseDetailSerializer(CourseSerializer):
    modules = ModuleSerializer(many=True, read_only=True)

    class Meta(CourseSerializer.Meta):
        fields = CourseSerializer.Meta.fields + ["modules"]


class EnrollmentSerializer(serializers.ModelSerializer):
    user = serializers.PrimaryKeyRelatedField(queryset=User.objects.all())
    course = serializers.PrimaryKeyRelatedField(queryset=Course.objects.all())

    class Meta:
        model = Enrollment
        fields = ["id", "user", "course", "progress", "status", "updated_at"]
        read_only_fields = ["id", "updated_at"]


class CertificateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Certificate
        fields = ["id", "enrollment", "certificate_id", "issued_at"]
        read_only_fields = ["id", "certificate_id", "issued_at"]


class LessonSerializer(serializers.ModelSerializer):
    class Meta:
        model = Lesson
        fields = [
            "id",
            "module",
            "title",
            "content_type",
            "language",
            "content",
            "media_url",
            "image_url",
            "assessment_type",
            "assessment_payload",
            "order",
        ]


class AssignProviderSerializer(serializers.Serializer):
    provider_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(role=User.ROLE_COURSE_PROVIDER), source="course_provider"
    )


class AssignOrganizationSerializer(serializers.Serializer):
    organization_id = serializers.PrimaryKeyRelatedField(
        queryset=Organization.objects.all(), allow_null=True, required=True, source="organization"
    )