from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework import decorators, permissions, response, status, viewsets
from rest_framework.exceptions import PermissionDenied, ValidationError

from core.permissions import IsCourseProvider
from .models import Assessment, AssessmentAttempt, AssessmentAnswer, Choice, Question
from .serializers import (
    AssessmentAnswerSerializer,
    AssessmentAttemptActionSerializer,
    AssessmentAttemptSerializer,
    AssessmentSerializer,
    ChoiceSerializer,
    QuestionSerializer,
    AssessmentSubmissionSerializer,
)
from .services import grade_attempt, save_attempt_response


class AssessmentViewSet(viewsets.ModelViewSet):
    queryset = Assessment.objects.select_related("lesson", "certificate_exam").prefetch_related(
        "questions__choices",
        "questions__matching_pairs",
        "questions__ordering_items",
        "attempts",
        "attempts__answers",
        "attempts__answers__selected_choices",
    )
    serializer_class = AssessmentSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ["lesson", "certificate_exam", "passing_score", "shuffle_questions"]
    search_fields = ["title", "description"]
    ordering_fields = ["created_at", "updated_at", "title"]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if not user.is_authenticated:
            return qs.none()
        if getattr(user, "role", None) == "super_admin":
            return qs
        owned_by_provider = Q(lesson__module__course__course_provider=user) | Q(certificate_exam__course__course_provider=user)
        enrolled_courses = user.enrollments.values_list("course_id", flat=True)
        enrolled_in = Q(lesson__module__course__in=enrolled_courses) | Q(certificate_exam__course__in=enrolled_courses)
        return qs.filter(owned_by_provider | enrolled_in)

    def get_permissions(self):
        if self.action in ["create", "update", "partial_update", "destroy"]:
            return [IsCourseProvider()]
        return super().get_permissions()

    def perform_create(self, serializer):
        serializer.save()

    def perform_update(self, serializer):
        serializer.save()

    @decorators.action(detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated])
    def start(self, request, pk=None):
        assessment = self.get_object()
        attempt_number = (
            assessment.attempts.filter(user=request.user).order_by("-attempt_number").values_list("attempt_number", flat=True).first()
            or 0
        ) + 1
        attempt = AssessmentAttempt.objects.create(
            assessment=assessment,
            user=request.user,
            attempt_number=attempt_number,
            status=AssessmentAttempt.STATUS_STARTED,
        )
        return response.Response(AssessmentAttemptSerializer(attempt).data, status=status.HTTP_201_CREATED)

    @decorators.action(detail=True, methods=["get"], permission_classes=[permissions.IsAuthenticated])
    def resume(self, request, pk=None):
        assessment = self.get_object()
        attempt = assessment.attempts.filter(user=request.user, status__in=[AssessmentAttempt.STATUS_STARTED, AssessmentAttempt.STATUS_IN_PROGRESS]).order_by("-attempt_number").first()
        if not attempt:
            return response.Response({"detail": "No active attempt"}, status=status.HTTP_404_NOT_FOUND)
        return response.Response(AssessmentAttemptSerializer(attempt).data)

    @decorators.action(detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated], url_path="save-progress")
    def save_progress(self, request, pk=None):
        assessment = self.get_object()
        attempt = assessment.attempts.filter(user=request.user, status__in=[AssessmentAttempt.STATUS_STARTED, AssessmentAttempt.STATUS_IN_PROGRESS]).order_by("-attempt_number").first()
        if not attempt:
            return response.Response({"detail": "No active attempt"}, status=status.HTTP_404_NOT_FOUND)
        serializer = AssessmentAttemptActionSerializer(data=request.data, context={"attempt": attempt})
        serializer.is_valid(raise_exception=True)
        attempt = serializer.save()
        return response.Response(AssessmentAttemptSerializer(attempt).data)

    @decorators.action(detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated])
    def submit(self, request, pk=None):
        assessment = self.get_object()
        attempt = assessment.attempts.filter(user=request.user, status__in=[AssessmentAttempt.STATUS_STARTED, AssessmentAttempt.STATUS_IN_PROGRESS]).order_by("-attempt_number").first()
        if not attempt:
            return response.Response({"detail": "No active attempt"}, status=status.HTTP_404_NOT_FOUND)
        serializer = AssessmentSubmissionSerializer(data=request.data, context={"attempt": attempt})
        serializer.is_valid(raise_exception=True)
        attempt = serializer.save()
        return response.Response(AssessmentAttemptSerializer(attempt).data)

    @decorators.action(detail=True, methods=["get"], permission_classes=[permissions.IsAuthenticated])
    def attempts(self, request, pk=None):
        assessment = self.get_object()
        qs = assessment.attempts.filter(user=request.user).order_by("-created_at")
        return response.Response(AssessmentAttemptSerializer(qs, many=True).data)


class QuestionViewSet(viewsets.ModelViewSet):
    queryset = Question.objects.select_related("assessment").prefetch_related("choices", "matching_pairs", "ordering_items")
    serializer_class = QuestionSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ["assessment", "type", "is_required"]
    search_fields = ["prompt", "explanation"]
    ordering_fields = ["order", "created_at"]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if not user.is_authenticated:
            return qs.none()
        if getattr(user, "role", None) == "super_admin":
            return qs
        return qs.filter(Q(assessment__lesson__module__course__course_provider=user) | Q(assessment__certificate_exam__course__course_provider=user))

    def get_permissions(self):
        if self.action in ["create", "update", "partial_update", "destroy"]:
            return [IsCourseProvider()]
        return super().get_permissions()


class ChoiceViewSet(viewsets.ModelViewSet):
    queryset = Choice.objects.select_related("question", "question__assessment")
    serializer_class = ChoiceSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ["question", "is_correct"]
    search_fields = ["text", "value"]
    ordering_fields = ["order", "created_at"]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if not user.is_authenticated:
            return qs.none()
        if getattr(user, "role", None) == "super_admin":
            return qs
        return qs.filter(Q(question__assessment__lesson__module__course__course_provider=user) | Q(question__assessment__certificate_exam__course__course_provider=user))

    def get_permissions(self):
        if self.action in ["create", "update", "partial_update", "destroy"]:
            return [IsCourseProvider()]
        return super().get_permissions()
