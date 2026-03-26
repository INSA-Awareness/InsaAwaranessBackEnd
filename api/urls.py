from django.urls import path, include
from rest_framework.routers import DefaultRouter

from accounts import urls as accounts_urls
from organizations.views import OrganizationViewSet, OrganizationMembershipViewSet
from courses.views import (
    CourseViewSet,
    ModuleViewSet,
    ArticleViewSet,
    VideoViewSet,
    CertificateExamViewSet,
    EnrollmentViewSet,
    CertificateViewSet,
    LessonViewSet,
)
from resources.views import ResourceViewSet
from campaigns.views import CampaignViewSet
from compliance.views import ComplianceReportViewSet
from training_requests.views import TrainingRequestViewSet
from finance.views import PaymentApprovalViewSet
from notifications.views import NotificationViewSet
from alerts.views import AlertViewSet, AlertDeliveryViewSet, AlertViewLogViewSet
from awareness_tools.views import AwarenessToolViewSet, AwarenessToolUsageViewSet, PublicAwarenessToolViewSet

router = DefaultRouter()
router.register(r"organizations", OrganizationViewSet, basename="organization")
router.register(r"memberships", OrganizationMembershipViewSet, basename="membership")
router.register(r"courses", CourseViewSet, basename="course")
router.register(r"modules", ModuleViewSet, basename="module")
router.register(r"articles", ArticleViewSet, basename="article")
router.register(r"videos", VideoViewSet, basename="video")
router.register(r"certificate-exams", CertificateExamViewSet, basename="certificate-exam")
router.register(r"lessons", LessonViewSet, basename="lesson")
router.register(r"enrollments", EnrollmentViewSet, basename="enrollment")
router.register(r"certificates", CertificateViewSet, basename="certificate")
router.register(r"resources", ResourceViewSet, basename="resource")
router.register(r"campaigns", CampaignViewSet, basename="campaign")
router.register(r"compliance-reports", ComplianceReportViewSet, basename="compliance-report")
router.register(r"training-requests", TrainingRequestViewSet, basename="training-request")
router.register(r"payment-approvals", PaymentApprovalViewSet, basename="payment-approval")
router.register(r"notifications", NotificationViewSet, basename="notification")
router.register(r"alerts", AlertViewSet, basename="alert")
router.register(r"alert-deliveries", AlertDeliveryViewSet, basename="alert-delivery")
router.register(r"alert-views", AlertViewLogViewSet, basename="alert-view")
router.register(r"awareness-tools", PublicAwarenessToolViewSet, basename="public-awareness-tool")
router.register(r"superadmin/awareness-tools", AwarenessToolViewSet, basename="awareness-tool")
router.register(r"superadmin/awareness-tool-usages", AwarenessToolUsageViewSet, basename="awareness-tool-usage")

urlpatterns = [
    path("auth/", include(accounts_urls)),
    path("v1/", include(router.urls)),
]