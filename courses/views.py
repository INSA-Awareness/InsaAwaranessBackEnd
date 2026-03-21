from django.db import transaction
from django.db.models import Q
from rest_framework import viewsets, permissions, decorators, response, status
from rest_framework.exceptions import PermissionDenied, ValidationError

from core.permissions import IsSuperAdmin, IsCourseProvider
from .models import Course, Module, Article, Video, Assessment, Enrollment, Certificate, Lesson, EnrollmentProfileSnapshot
from .models import AssessmentAttempt
from accounts.models import BackgroundProfile, User
from .serializers import (
    CourseSerializer,
    CourseDetailSerializer,
    ModuleSerializer,
    ArticleSerializer,
    VideoSerializer,
    AssessmentSerializer,
    EnrollmentSerializer,
    CertificateSerializer,
    LessonSerializer,
    AssessmentAttemptSerializer,
    AssignProviderSerializer,
    AssignOrganizationSerializer,
)


class CourseViewSet(viewsets.ModelViewSet):
    queryset = Course.objects.select_related("organization", "created_by", "assigned_by", "course_provider").prefetch_related("modules", "modules__lessons")
    serializer_class = CourseSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ["language", "status", "organization"]
    search_fields = ["title", "description"]
    ordering_fields = ["created_at", "title"]

    def get_queryset(self):
        qs = Course.objects.select_related("organization", "created_by", "assigned_by", "course_provider").prefetch_related("modules", "modules__lessons")
        user = self.request.user
        if not user or not user.is_authenticated:
            return qs.none()

        role = user.role
        if role == User.ROLE_SUPER_ADMIN:
            return qs
        if role == User.ROLE_COURSE_PROVIDER:
            return qs.filter(course_provider=user)
        if role in {User.ROLE_ORG_ADMIN, User.ROLE_MEMBER}:
            org_ids = user.memberships.values_list("organization_id", flat=True)
            return qs.filter(organization_id__in=org_ids)
        if role == User.ROLE_PUBLIC:
            return qs.filter(organization__isnull=True)
        return qs.none()

    def get_serializer_class(self):
        if self.action in ["retrieve", "list"]:
            return CourseDetailSerializer
        return CourseSerializer

    def get_permissions(self):
        if self.action in ["create", "update", "partial_update", "destroy"]:
            return [IsCourseProvider()]
        return super().get_permissions()

    def perform_create(self, serializer):
        user = self.request.user
        organization = serializer.validated_data.get("organization")
        provider = serializer.validated_data.get("course_provider")

        if user.role == User.ROLE_COURSE_PROVIDER:
            provider = user
            if organization:
                raise ValidationError({"organization": "Only super_admin can assign organizations."})
            organization = None
        elif user.role == User.ROLE_SUPER_ADMIN:
            if provider is None:
                raise ValidationError({"course_provider": "course_provider is required"})
        else:
            raise PermissionDenied("Not allowed to create courses")

        serializer.save(
            created_by=user,
            course_provider=provider,
            organization=organization,
            language=serializer.validated_data.get("language", getattr(user, "preferred_language", "en")),
        )

    def perform_update(self, serializer):
        instance = serializer.instance
        user = self.request.user

        if user.role != User.ROLE_SUPER_ADMIN:
            if instance.course_provider != user:
                raise PermissionDenied("You cannot modify a course you do not own")
            # block provider/org changes
            incoming_provider = serializer.validated_data.get("course_provider")
            incoming_org = serializer.validated_data.get("organization")
            if incoming_provider and incoming_provider != instance.course_provider:
                raise ValidationError({"course_provider": "Only super_admin can reassign course providers."})
            if incoming_org is not None and incoming_org != instance.organization:
                raise ValidationError({"organization": "Only super_admin can assign organizations."})

        serializer.save()

    def perform_destroy(self, instance):
        user = self.request.user
        if user.role != User.ROLE_SUPER_ADMIN and instance.course_provider != user:
            raise PermissionDenied("You cannot delete a course you do not own")
        instance.delete()

    @decorators.action(detail=True, methods=["post"], permission_classes=[IsSuperAdmin], url_path="assign-provider")
    def assign_provider(self, request, pk=None):
        course = self.get_object()
        serializer = AssignProviderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        course.course_provider = serializer.validated_data["course_provider"]
        course.assigned_by = request.user
        course.save()
        return response.Response({"detail": "Course provider assigned"})

    @decorators.action(detail=True, methods=["post"], permission_classes=[IsSuperAdmin], url_path="assign-organization")
    def assign_organization(self, request, pk=None):
        course = self.get_object()
        serializer = AssignOrganizationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        course.organization = serializer.validated_data["organization"]
        course.assigned_by = request.user
        course.save()
        return response.Response({"detail": "Course organization assigned"})


class ModuleViewSet(viewsets.ModelViewSet):
    queryset = Module.objects.select_related("course")
    serializer_class = ModuleSerializer
    permission_classes = [permissions.IsAuthenticated, IsCourseProvider]
    filterset_fields = ["course"]
    search_fields = ["title"]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if not user or not user.is_authenticated:
            return qs.none()
        if user.role != User.ROLE_SUPER_ADMIN:
            qs = qs.filter(course__course_provider=user)
        return qs


class ArticleViewSet(viewsets.ModelViewSet):
    queryset = Article.objects.select_related("module", "module__course")
    serializer_class = ArticleSerializer
    permission_classes = [permissions.IsAuthenticated, IsCourseProvider]
    filterset_fields = ["module"]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if not user or not user.is_authenticated:
            return qs.none()
        return qs

    def get_permissions(self):
        if self.action in ["create", "update", "partial_update", "destroy"]:
            return [permissions.IsAuthenticated(), IsCourseProvider()]
        return [permissions.IsAuthenticated()]


class VideoViewSet(viewsets.ModelViewSet):
    queryset = Video.objects.select_related("module", "module__course")
    serializer_class = VideoSerializer
    permission_classes = [permissions.IsAuthenticated, IsCourseProvider]
    filterset_fields = ["module"]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if not user or not user.is_authenticated:
            return qs.none()
        if user.role != User.ROLE_SUPER_ADMIN:
            qs = qs.filter(module__course__course_provider=user)
        return qs

    @decorators.action(detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated], url_path="submit")
    def submit(self, request, pk=None):
        lesson = self.get_object()
        payload = lesson.assessment_payload or {}
        questions = payload.get("questions") or []
        answers = request.data.get("answers", {}) or {}
        if not questions:
            return response.Response({"detail": "No assessment configured"}, status=status.HTTP_400_BAD_REQUEST)

        total_questions = len(questions)
        correct_count = 0
        details = []

        for q in questions:
            qid = q.get("id")
            qtype = q.get("type")
            correct_answer = q.get("correct_answer")
            user_answer = answers.get(qid)
            is_correct = False
            if qtype == Lesson.ASSESSMENT_MULTIPLE_CHOICE:
                is_correct = user_answer == correct_answer
            elif qtype == Lesson.ASSESSMENT_TRUE_FALSE:
                is_correct = bool(user_answer) == bool(correct_answer)
            elif qtype == Lesson.ASSESSMENT_MATCHING:
                is_correct = isinstance(user_answer, dict) and user_answer == correct_answer
            details.append({"question_id": qid, "is_correct": is_correct})
            if is_correct:
                correct_count += 1

        score = (correct_count / total_questions) * 100 if total_questions else 0
        attempt = AssessmentAttempt.objects.create(
            user=request.user,
            lesson=lesson,
            answers=answers,
            score=score,
            total_questions=total_questions,
            correct_answers=correct_count,
        )
        return response.Response(
            {
                "score": score,
                "correct_answers": correct_count,
                "total_questions": total_questions,
                "details": details,
                "attempt_id": str(attempt.id),
            }
        )

    @decorators.action(detail=True, methods=["get"], permission_classes=[permissions.IsAuthenticated], url_path="attempts")
    def attempts(self, request, pk=None):
        lesson = self.get_object()
        qs = lesson.assessment_attempts.filter(user=request.user).order_by("-created_at")
        data = AssessmentAttemptSerializer(qs, many=True).data
        return response.Response(data)

    @decorators.action(
        detail=True,
        methods=["get"],
        permission_classes=[permissions.IsAuthenticated],
        url_path=r"attempts/(?P<attempt_id>[0-9a-f-]{36})",
    )
    def attempt_detail(self, request, pk=None, attempt_id=None):
        lesson = self.get_object()
        attempt = lesson.assessment_attempts.filter(user=request.user, id=attempt_id).first()
        if not attempt:
            return response.Response({"detail": "Not found"}, status=status.HTTP_404_NOT_FOUND)
        data = AssessmentAttemptSerializer(attempt).data
        return response.Response(data)


class AssessmentViewSet(viewsets.ModelViewSet):
    queryset = Assessment.objects.select_related("module", "module__course")
    serializer_class = AssessmentSerializer
    permission_classes = [permissions.IsAuthenticated, IsCourseProvider]
    filterset_fields = ["module"]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if not user or not user.is_authenticated:
            return qs.none()
        if user.role != User.ROLE_SUPER_ADMIN:
            qs = qs.filter(module__course__course_provider=user)
        return qs


class LessonViewSet(viewsets.ModelViewSet):
    queryset = Lesson.objects.select_related("module", "module__course")
    serializer_class = LessonSerializer
    permission_classes = [permissions.IsAuthenticated, IsCourseProvider]
    filterset_fields = ["content_type", "language", "module__course__language"]
    search_fields = ["title"]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if not user or not user.is_authenticated:
            return qs.none()
        if user.role != User.ROLE_SUPER_ADMIN:
            qs = qs.filter(module__course__course_provider=user)
        return qs


class EnrollmentViewSet(viewsets.ModelViewSet):
    queryset = Enrollment.objects.select_related("user", "course")
    serializer_class = EnrollmentSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ["user", "course", "status"]

    def _ensure_public_profile(self, user):
        if getattr(user, "role", None) != User.ROLE_PUBLIC:
            return None
        profile, _ = BackgroundProfile.objects.get_or_create(user=user)
        if profile.is_complete():
            return None
        return {
            "status": "profile_required",
            "message": "Complete your background profile before enrolling in any course.",
            "profile_completion_endpoint": "/api/auth/user/background-profile/",
        }

    def _validate_org_admin_enrollment(self, acting_user, data):
        if getattr(acting_user, "role", None) != User.ROLE_ORG_ADMIN:
            return
        target_user = data.get("user")
        course = data.get("course")
        if not target_user or not course:
            return
        org_ids = set(acting_user.memberships.values_list("organization_id", flat=True))
        if not org_ids:
            raise PermissionDenied("You are not assigned to any organization")
        user_org_ids = set(target_user.memberships.values_list("organization_id", flat=True))
        if not (org_ids & user_org_ids):
            raise PermissionDenied("User is not in your organization")
        if course.organization_id and course.organization_id not in org_ids:
            raise PermissionDenied("Course is not in your organization")

    def perform_update(self, serializer):
        enrollment: Enrollment = serializer.instance
        self._check_object_permission(self.request, enrollment)
        with transaction.atomic():
            enrollment = serializer.save()
            if enrollment.status == Enrollment.STATUS_COMPLETED and not hasattr(enrollment, "certificate"):
                Certificate.objects.create(enrollment=enrollment)

    def create(self, request, *args, **kwargs):
        profile_block = self._ensure_public_profile(request.user)
        if profile_block:
            return response.Response(profile_block, status=status.HTTP_400_BAD_REQUEST)
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self._validate_org_admin_enrollment(request.user, serializer.validated_data)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return response.Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    def update(self, request, *args, **kwargs):
        profile_block = self._ensure_public_profile(request.user)
        if profile_block:
            return response.Response(profile_block, status=status.HTTP_400_BAD_REQUEST)
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        validated = serializer.validated_data
        self._validate_org_admin_enrollment(
            request.user,
            {
                "user": validated.get("user", instance.user),
                "course": validated.get("course", instance.course),
            },
        )
        self.perform_update(serializer)
        return response.Response(serializer.data)

    def _check_object_permission(self, request, enrollment: Enrollment):
        user = request.user
        if not user or not user.is_authenticated:
            raise permissions.PermissionDenied("Authentication required")
        if getattr(user, "role", None) == User.ROLE_SUPER_ADMIN:
            return
        if enrollment.user_id == user.id:
            return
        # Allow course provider to update enrollments for their course
        if enrollment.course and enrollment.course.course_provider_id == user.id:
            return
        raise permissions.PermissionDenied("You cannot modify this enrollment")

    def partial_update(self, request, *args, **kwargs):
        profile_block = self._ensure_public_profile(request.user)
        if profile_block:
            return response.Response(profile_block, status=status.HTTP_400_BAD_REQUEST)
        kwargs["partial"] = True
        return self.update(request, *args, **kwargs)

    def perform_create(self, serializer):
        enrollment = serializer.save()
        user = enrollment.user
        if getattr(user, "role", None) == User.ROLE_PUBLIC:
            profile, _ = BackgroundProfile.objects.get_or_create(user=user)
            EnrollmentProfileSnapshot.objects.create(
                enrollment=enrollment,
                user=user,
                course=enrollment.course,
                nationality=profile.nationality,
                region=profile.region,
                age_range=profile.age_range,
                phone_number=profile.phone_number,
                gender=profile.gender,
                education_level=profile.education_level,
                field_of_study=profile.field_of_study,
                institution_name=profile.institution_name,
                employment_status=profile.employment_status,
                employer_name=profile.employer_name,
                unemployment_description=profile.unemployment_description,
                professional_experience=profile.professional_experience,
                enrollment_motivation=profile.enrollment_motivation,
                referral_source=profile.referral_source,
                is_information_confirmed=profile.is_information_confirmed,
            )


class CertificateViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Certificate.objects.select_related("enrollment", "enrollment__course", "enrollment__user")
    serializer_class = CertificateSerializer
    permission_classes = [permissions.IsAuthenticated]