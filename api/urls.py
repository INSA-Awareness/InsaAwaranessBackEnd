from django.urls import path, include
from rest_framework.routers import DefaultRouter

from accounts import urls as accounts_urls
from organizations.views import OrganizationViewSet, OrganizationMembershipViewSet
from courses.views import (
    CourseViewSet,
    ModuleViewSet,
    ArticleViewSet,
    VideoViewSet,
    AssessmentViewSet,
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

router = DefaultRouter()
router.register(r"organizations", OrganizationViewSet, basename="organization")
router.register(r"memberships", OrganizationMembershipViewSet, basename="membership")
router.register(r"courses", CourseViewSet, basename="course")
router.register(r"modules", ModuleViewSet, basename="module")
router.register(r"articles", ArticleViewSet, basename="article")
router.register(r"videos", VideoViewSet, basename="video")
router.register(r"assessments", AssessmentViewSet, basename="assessment")
router.register(r"lessons", LessonViewSet, basename="lesson")
router.register(r"enrollments", EnrollmentViewSet, basename="enrollment")
router.register(r"certificates", CertificateViewSet, basename="certificate")
router.register(r"resources", ResourceViewSet, basename="resource")
router.register(r"campaigns", CampaignViewSet, basename="campaign")
router.register(r"compliance-reports", ComplianceReportViewSet, basename="compliance-report")
router.register(r"training-requests", TrainingRequestViewSet, basename="training-request")
router.register(r"payment-approvals", PaymentApprovalViewSet, basename="payment-approval")
router.register(r"notifications", NotificationViewSet, basename="notification")

urlpatterns = [
    path("auth/", include(accounts_urls)),
    path("v1/", include(router.urls)),
]