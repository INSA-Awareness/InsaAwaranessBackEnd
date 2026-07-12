from django.contrib.auth import get_user_model
from django.db.models import Count, Avg
from rest_framework import viewsets, permissions, decorators, response

from core.permissions import IsSuperAdmin
from courses.models import Course, Enrollment, AssessmentAttempt, Certificate
from alerts.models import Alert

User = get_user_model()


class AnalyticsViewSet(viewsets.ViewSet):
    permission_classes = [permissions.IsAuthenticated, IsSuperAdmin]

    @decorators.action(detail=False, methods=["get"], url_path="dashboard")
    def dashboard(self, request):
        total_users = User.objects.count()
        users_by_role = dict(
            User.objects.values("role").annotate(count=Count("id")).values_list("role", "count")
        )
        total_courses = Course.objects.count()
        courses_by_status = dict(
            Course.objects.values("status").annotate(count=Count("id")).values_list("status", "count")
        )
        total_enrollments = Enrollment.objects.count()
        enrollments_by_status = dict(
            Enrollment.objects.values("status").annotate(count=Count("id")).values_list("status", "count")
        )
        avg_progress = Enrollment.objects.aggregate(avg=Avg("progress"))["avg"] or 0
        total_certificates = Certificate.objects.count()
        total_attempts = AssessmentAttempt.objects.count()
        avg_score = AssessmentAttempt.objects.aggregate(avg=Avg("score"))["avg"] or 0
        total_alerts = Alert.objects.count()
        published_alerts = Alert.objects.filter(status=Alert.STATUS_PUBLISHED).count()

        return response.Response({
            "users": {
                "total": total_users,
                "by_role": users_by_role,
            },
            "courses": {
                "total": total_courses,
                "by_status": courses_by_status,
            },
            "enrollments": {
                "total": total_enrollments,
                "by_status": enrollments_by_status,
                "average_progress": round(avg_progress, 1),
            },
            "certificates": {
                "total": total_certificates,
            },
            "assessments": {
                "total_attempts": total_attempts,
                "average_score": round(avg_score, 1),
            },
            "alerts": {
                "total": total_alerts,
                "published": published_alerts,
            },
        })
