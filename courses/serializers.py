from django.contrib.auth import get_user_model
from rest_framework import serializers

from organizations.models import Organization
from .models import (
    Course,
    Module,
    Article,
    Video,
    Assessment,
    Enrollment,
    Certificate,
    Lesson,
    AssessmentAttempt,
)

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
            "thumbnail_url",
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
    def _validate_assessment_payload(self, value):
        if value in [None, ""]:
            return {}
        if not isinstance(value, dict):
            raise serializers.ValidationError("assessment_payload must be an object")
        questions = value.get("questions")
        if not isinstance(questions, list) or not questions:
            raise serializers.ValidationError("assessment_payload.questions must be a non-empty list")
        for q in questions:
            if not isinstance(q, dict):
                raise serializers.ValidationError("Each question must be an object")
            for field in ["id", "type", "question", "correct_answer"]:
                if field not in q:
                    raise serializers.ValidationError(f"Question missing '{field}'")
            q_type = q.get("type")
            if q_type not in [
                Lesson.ASSESSMENT_MULTIPLE_CHOICE,
                Lesson.ASSESSMENT_TRUE_FALSE,
                Lesson.ASSESSMENT_MATCHING,
            ]:
                raise serializers.ValidationError(f"Unsupported question type: {q_type}")
            if q_type == Lesson.ASSESSMENT_MULTIPLE_CHOICE:
                options = q.get("options")
                if not isinstance(options, list) or not options:
                    raise serializers.ValidationError("multiple_choice questions require options")
                option_ids = {opt.get("id") for opt in options if isinstance(opt, dict)}
                if q.get("correct_answer") not in option_ids:
                    raise serializers.ValidationError("correct_answer must match an option id")
            elif q_type == Lesson.ASSESSMENT_TRUE_FALSE:
                if not isinstance(q.get("correct_answer"), bool):
                    raise serializers.ValidationError("true_false correct_answer must be boolean")
            elif q_type == Lesson.ASSESSMENT_MATCHING:
                if not isinstance(q.get("correct_answer"), dict):
                    raise serializers.ValidationError("matching correct_answer must be an object of pairs")
        return value

    def validate(self, attrs):
        attrs = super().validate(attrs)
        if attrs.get("content_type") == Lesson.TYPE_ASSESSMENT:
            payload = attrs.get("assessment_payload", getattr(self.instance, "assessment_payload", {}))
            attrs["assessment_payload"] = self._validate_assessment_payload(payload)
        return attrs

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get("request")
        user = getattr(request, "user", None)
        role = getattr(user, "role", None)
        is_admin = role in {User.ROLE_SUPER_ADMIN, User.ROLE_COURSE_PROVIDER}
        if not is_admin and data.get("assessment_payload"):
            payload = data["assessment_payload"] or {}
            questions = payload.get("questions")
            if isinstance(questions, list):
                for q in questions:
                    q.pop("correct_answer", None)
            data["assessment_payload"] = payload
        return data

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


class AssessmentAttemptSerializer(serializers.ModelSerializer):
    class Meta:
        model = AssessmentAttempt
        fields = [
            "id",
            "lesson",
            "answers",
            "score",
            "total_questions",
            "correct_answers",
            "created_at",
        ]
        read_only_fields = fields


class AssignProviderSerializer(serializers.Serializer):
    provider_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(role=User.ROLE_COURSE_PROVIDER), source="course_provider"
    )


class AssignOrganizationSerializer(serializers.Serializer):
    organization_id = serializers.PrimaryKeyRelatedField(
        queryset=Organization.objects.all(), allow_null=True, required=True, source="organization"
    )