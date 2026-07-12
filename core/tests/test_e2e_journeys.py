import uuid
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.core.files.base import ContentFile
from rest_framework import status
from rest_framework.test import APITestCase
from django.core import mail

from accounts.models import User, BackgroundProfile
from organizations.models import Organization, OrganizationMembership, OrganizationApplication
from courses.models import Course, Module, Lesson, Article, Video, Enrollment, Certificate, LessonProgress
from assessment.models import Assessment, Question, Choice
from alerts.models import Alert
from campaigns.models import Campaign
from notifications.models import Notification
from resources.models import Resource
from training_requests.models import TrainingRequest
from finance.models import PaymentApproval
from awareness_tools.models import AwarenessTool
from audit.models import AuditLog
from compliance.models import ComplianceReport


def _create_user(email, password="TestPass123!", **kwargs):
    defaults = {"role": User.ROLE_MEMBER, "is_active": True, "email_verified": True}
    defaults.update(kwargs)
    return User.objects.create_user(email=email, password=password, **defaults)


def _create_org(name="Test Org", created_by=None):
    return Organization.objects.create(name=name, created_by=created_by)


def _create_membership(user, org, org_role=OrganizationMembership.ROLE_MEMBER, is_primary=True):
    return OrganizationMembership.objects.create(
        user=user, organization=org, org_role=org_role, is_primary=is_primary
    )


def _create_course(provider, **kwargs):
    defaults = {
        "title": "Test Course",
        "description": "A test course",
        "level": "Beginner",
        "status": Course.STATUS_PUBLISHED,
        "language": "en",
        "is_active": True,
    }
    defaults.update(kwargs)
    return Course.objects.create(course_provider=provider, created_by=provider, **defaults)


def _create_module(course, title="Test Module", order=1):
    return Module.objects.create(course=course, title=title, order=order)


def _create_lesson(module, title="Test Lesson", content_type=Lesson.TYPE_ARTICLE, order=1, **kwargs):
    defaults = {"language": "en", "content": "Lesson content here"}
    defaults.update(kwargs)
    return Lesson.objects.create(module=module, title=title, content_type=content_type, order=order, **defaults)


# ---------------------------------------------------------------------------
# 1. PUBLIC USER JOURNEY
# ---------------------------------------------------------------------------
class TestPublicUserJourney(APITestCase):
    """Registration, email verification, login, password reset, browse public content."""

    def test_01_registration_flow(self):
        resp = self.client.post("/api/auth/register/", {
            "email": "newuser@example.com",
            "password": "StrongPass1!",
            "first_name": "New",
            "last_name": "User",
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        user = User.objects.get(email="newuser@example.com")
        self.assertEqual(user.role, User.ROLE_PUBLIC)
        self.assertFalse(user.is_active)
        self.assertFalse(user.email_verified)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("verify", mail.outbox[0].subject.lower())

    def test_02_email_verification(self):
        user = User.objects.create_user(
            email="verify@example.com", password="TestPass123!",
            role=User.ROLE_PUBLIC, is_active=False, email_verified=False
        )
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        resp = self.client.post("/api/auth/verify-email/", {"uid": uid, "token": token}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        user.refresh_from_db()
        self.assertTrue(user.email_verified)
        self.assertTrue(user.is_active)

    def test_03_email_verification_invalid_token(self):
        user = User.objects.create_user(
            email="badverify@example.com", password="TestPass123!", role=User.ROLE_PUBLIC
        )
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        resp = self.client.post("/api/auth/verify-email/", {"uid": uid, "token": "bad-token"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_04_login_success(self):
        user = _create_user("login@example.com", role=User.ROLE_MEMBER)
        resp = self.client.post("/api/auth/login/", {
            "email": "login@example.com",
            "password": "TestPass123!",
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("access", resp.data)
        self.assertIn("refresh", resp.data)
        self.assertIn("user", resp.data)
        self.assertEqual(resp.data["user"]["email"], "login@example.com")
        self.assertEqual(resp.data["user"]["role"], User.ROLE_MEMBER)

    def test_05_login_invalid_credentials(self):
        _create_user("loginfail@example.com")
        resp = self.client.post("/api/auth/login/", {
            "email": "loginfail@example.com",
            "password": "WrongPassword1!",
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_06_login_inactive_user_blocked(self):
        User.objects.create_user(
            email="inactive@example.com", password="TestPass123!",
            role=User.ROLE_MEMBER, is_active=False
        )
        resp = self.client.post("/api/auth/login/", {
            "email": "inactive@example.com",
            "password": "TestPass123!",
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_07_password_reset_flow(self):
        user = _create_user("reset@example.com")
        resp = self.client.post("/api/auth/password-reset/", {"email": "reset@example.com"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(mail.outbox), 1)
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        resp2 = self.client.post("/api/auth/password-reset/confirm/", {
            "uid": uid, "token": token, "new_password": "NewStrongPass1!",
        }, format="json")
        self.assertEqual(resp2.status_code, status.HTTP_200_OK)
        user.refresh_from_db()
        self.assertTrue(user.check_password("NewStrongPass1!"))

    def test_08_password_reset_invalid_token(self):
        _create_user("resetbad@example.com")
        uid = urlsafe_base64_encode(force_bytes(uuid.uuid4()))
        resp = self.client.post("/api/auth/password-reset/confirm/", {
            "uid": uid, "token": "bad", "new_password": "NewStrongPass1!",
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_09_me_endpoint(self):
        user = _create_user("me@example.com", role=User.ROLE_MEMBER)
        self.client.force_authenticate(user)
        resp = self.client.get("/api/auth/me/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["email"], "me@example.com")

    def test_10_me_unauthenticated(self):
        resp = self.client.get("/api/auth/me/")
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_11_change_password(self):
        user = _create_user("changepw@example.com")
        self.client.force_authenticate(user)
        resp = self.client.put("/api/auth/change-password/", {
            "old_password": "TestPass123!",
            "new_password": "NewStrongPass1!",
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        user.refresh_from_db()
        self.assertTrue(user.check_password("NewStrongPass1!"))

    def test_12_change_password_wrong_old(self):
        user = _create_user("changepwbad@example.com")
        self.client.force_authenticate(user)
        resp = self.client.put("/api/auth/change-password/", {
            "old_password": "WrongOldPass1!",
            "new_password": "NewStrongPass1!",
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_13_browse_courses_unauthenticated(self):
        provider = _create_user("provider@example.com", role=User.ROLE_COURSE_PROVIDER)
        _create_course(provider, status=Course.STATUS_PUBLISHED)
        _create_course(provider, title="Draft Course", status=Course.STATUS_DRAFT)
        resp = self.client.get("/api/v1/courses/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        results = resp.data.get("results") or resp.data
        titles = [c["title"] for c in results]
        self.assertIn("Test Course", titles)
        self.assertNotIn("Draft Course", titles)

    def test_14_browse_resources_unauthenticated(self):
        provider = _create_user("resprovider@example.com", role=User.ROLE_COURSE_PROVIDER)
        Resource.objects.create(
            title="Public Resource", content="Content here",
            status=Resource.STATUS_PUBLISHED, created_by=provider, category="pdf", audience="general"
        )
        Resource.objects.create(
            title="Draft Resource", content="Draft",
            status=Resource.STATUS_DRAFT, created_by=provider, category="pdf", audience="general"
        )
        resp = self.client.get("/api/v1/resources/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        results = resp.data.get("results") or resp.data
        titles = [r["title"] for r in results]
        self.assertIn("Public Resource", titles)
        self.assertNotIn("Draft Resource", titles)

    def test_15_browse_alerts_unauthenticated(self):
        admin = _create_user("alertadmin@example.com", role=User.ROLE_SUPER_ADMIN)
        Alert.objects.create(title="Active Alert", message="Stay safe", severity=Alert.SEVERITY_HIGH,
                             status=Alert.STATUS_PUBLISHED, created_by=admin)
        Alert.objects.create(title="Draft Alert", message="Draft", severity=Alert.SEVERITY_LOW,
                             status=Alert.STATUS_DRAFT, created_by=admin)
        resp = self.client.get("/api/v1/alerts/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        results = resp.data.get("results") or resp.data
        titles = [a["title"] for a in results]
        self.assertIn("Active Alert", titles)
        self.assertNotIn("Draft Alert", titles)

    def test_16_browse_campaigns_unauthenticated(self):
        admin = _create_user("campadmin@example.com", role=User.ROLE_SUPER_ADMIN)
        Campaign.objects.create(title="Live Campaign", message="Live!", channels=["email"],
                                start_date="2025-01-01", status=Campaign.STATUS_LIVE, created_by=admin)
        Campaign.objects.create(title="Draft Campaign", message="Draft", channels=["email"],
                                start_date="2025-01-01", status=Campaign.STATUS_DRAFT, created_by=admin)
        resp = self.client.get("/api/v1/campaigns/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        results = resp.data.get("results") or resp.data
        titles = [c["title"] for c in results]
        self.assertIn("Live Campaign", titles)
        self.assertNotIn("Draft Campaign", titles)

    def test_17_browse_awareness_tools_unauthenticated(self):
        admin = _create_user("tooladmin@example.com", role=User.ROLE_SUPER_ADMIN)
        AwarenessTool.objects.create(name="Password Checker", description="Check passwords",
                                     status=AwarenessTool.STATUS_ENABLED, created_by=admin)
        AwarenessTool.objects.create(name="Disabled Tool", description="Disabled",
                                     status=AwarenessTool.STATUS_DISABLED, created_by=admin)
        resp = self.client.get("/api/v1/awareness-tools/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        results = resp.data.get("results") or resp.data
        names = [t["name"] for t in results]
        self.assertIn("Password Checker", names)
        self.assertNotIn("Disabled Tool", names)

    def test_18_organization_application(self):
        resp = self.client.post("/api/v1/organization-applications/", {
            "name": "New Org",
            "description": "We want to join",
            "contact_email": "contact@neworg.com",
            "contact_phone": "+251911111111",
            "address": "Addis Ababa, Ethiopia",
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data["status"], OrganizationApplication.STATUS_PENDING)

    def test_19_certificate_verification(self):
        provider = _create_user("certprov@example.com", role=User.ROLE_COURSE_PROVIDER)
        course = _create_course(provider, title="Cert Course")
        member = _create_user("certmember@example.com")
        enrollment = Enrollment.objects.create(user=member, course=course, progress=100,
                                                status=Enrollment.STATUS_COMPLETED)
        cert = Certificate.objects.create(enrollment=enrollment)
        resp = self.client.get(f"/api/v1/certificates/verify/{cert.certificate_id}/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data["valid"])
        self.assertEqual(resp.data["user"], "certmember@example.com")

    def test_20_certificate_verification_not_found(self):
        resp = self.client.get(f"/api/v1/certificates/verify/{uuid.uuid4()}/")
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_21_resend_verification(self):
        user = User.objects.create_user(
            email="resend@example.com", password="TestPass123!",
            role=User.ROLE_PUBLIC, is_active=False, email_verified=False
        )
        resp = self.client.post("/api/auth/resend-verification/", {"email": "resend@example.com"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(mail.outbox), 1)

    def test_22_resend_verification_already_verified(self):
        user = _create_user("alreadyverified@example.com", email_verified=True)
        resp = self.client.post("/api/auth/resend-verification/", {"email": "alreadyverified@example.com"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_23_background_profile_create(self):
        user = _create_user("bgprofile@example.com", role=User.ROLE_PUBLIC)
        self.client.force_authenticate(user)
        resp = self.client.get("/api/auth/user/background-profile/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_24_background_profile_update(self):
        user = _create_user("bgprofile2@example.com", role=User.ROLE_PUBLIC)
        self.client.force_authenticate(user)
        resp = self.client.put("/api/auth/user/background-profile/", {
            "nationality": "ethiopia",
            "region": "addis_ababa",
            "age_range": "26_30",
            "phone_number": "+251911111111",
            "gender": "male",
            "education_level": "bachelor",
            "field_of_study": "cs_it",
            "institution_name": "AAU",
            "employment_status": "full_time",
            "employer_name": "Tech Corp",
            "unemployment_description": "",
            "professional_experience": "3_5",
            "enrollment_motivation": "new_skill",
            "referral_source": "email",
            "is_information_confirmed": True,
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        profile = BackgroundProfile.objects.get(user=user)
        self.assertTrue(profile.is_complete())

    def test_25_login_returns_user_and_route(self):
        user = _create_user("loginroute@example.com", role=User.ROLE_MEMBER)
        resp = self.client.post("/api/auth/login/", {
            "email": "loginroute@example.com", "password": "TestPass123!",
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("dashboard_route", resp.data)
        self.assertIn("must_change_password", resp.data)
        self.assertEqual(resp.data["dashboard_route"], "/dashboard/member")


# ---------------------------------------------------------------------------
# 2. MEMBER JOURNEY
# ---------------------------------------------------------------------------
class TestMemberJourney(APITestCase):
    """Enroll in courses, complete lessons, take assessments, get certificates."""

    def setUp(self):
        self.provider = _create_user("courseprov@example.com", role=User.ROLE_COURSE_PROVIDER)
        self.course = _create_course(self.provider)
        self.module = _create_module(self.course)
        self.article_lesson = _create_lesson(self.module, title="Article 1", content_type=Lesson.TYPE_ARTICLE)
        self.video_lesson = _create_lesson(self.module, title="Video 1", content_type=Lesson.TYPE_VIDEO,
                                            media_url="https://example.com/video.mp4")
        self.assessment_lesson = _create_lesson(
            self.module, title="Quiz 1", content_type=Lesson.TYPE_ASSESSMENT,
            assessment_type=Lesson.ASSESSMENT_MULTIPLE_CHOICE,
            assessment_payload={
                "questions": [{
                    "id": "q1", "type": "multiple_choice", "question": "Pick A?",
                    "correct_answer": "a1",
                    "options": [{"id": "a1", "text": "Option A"}, {"id": "a2", "text": "Option B"}]
                }]
            },
            passing_score=50
        )
        self.normalized_assessment = Assessment.objects.create(
            lesson=self.assessment_lesson, title="Quiz 1", passing_score=50
        )
        self.question = Question.objects.create(
            assessment=self.normalized_assessment, type=Question.TYPE_MULTIPLE_CHOICE,
            prompt="Pick A?", order=1, points=5
        )
        self.correct_choice = Choice.objects.create(
            question=self.question, text="Option A", value="a1", is_correct=True, order=1
        )
        Choice.objects.create(question=self.question, text="Option B", value="a2", is_correct=False, order=2)
        self.member = _create_user("member@example.com", role=User.ROLE_MEMBER)
        self.client.force_authenticate(self.member)

    def test_01_browse_course_detail(self):
        resp = self.client.get(f"/api/v1/courses/{self.course.id}/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("modules", resp.data)

    def test_02_enroll_in_course(self):
        resp = self.client.post("/api/v1/enrollments/", {
            "user": str(self.member.id),
            "course": str(self.course.id),
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertTrue(Enrollment.objects.filter(user=self.member, course=self.course).exists())

    def test_03_enroll_duplicate_blocked(self):
        Enrollment.objects.get_or_create(user=self.member, course=self.course)
        resp = self.client.post("/api/v1/enrollments/", {
            "user": str(self.member.id),
            "course": str(self.course.id),
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_04_view_my_enrollments(self):
        Enrollment.objects.get_or_create(user=self.member, course=self.course)
        resp = self.client.get("/api/v1/enrollments/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        results = resp.data.get("results") or resp.data
        self.assertEqual(len(results), 1)

    def test_05_mark_lesson_progress(self):
        Enrollment.objects.get_or_create(user=self.member, course=self.course)
        resp = self.client.post("/api/v1/lesson-progress/", {
            "lesson": str(self.article_lesson.id),
            "completed": True,
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertTrue(LessonProgress.objects.filter(user=self.member, lesson=self.article_lesson, completed=True).exists())

    def test_06_progress_recalculates_enrollment(self):
        Enrollment.objects.get_or_create(user=self.member, course=self.course)
        self.client.post("/api/v1/lesson-progress/", {
            "lesson": str(self.article_lesson.id), "completed": True,
        }, format="json")
        self.client.post("/api/v1/lesson-progress/", {
            "lesson": str(self.video_lesson.id), "completed": True,
        }, format="json")
        self.client.post("/api/v1/lesson-progress/", {
            "lesson": str(self.assessment_lesson.id), "completed": True,
        }, format="json")
        enrollment = Enrollment.objects.get(user=self.member, course=self.course)
        self.assertEqual(enrollment.progress, 100)
        self.assertEqual(enrollment.status, Enrollment.STATUS_COMPLETED)
        self.assertTrue(hasattr(enrollment, "certificate"))

    def test_07_certificate_generated_on_completion(self):
        enrollment, _ = Enrollment.objects.get_or_create(user=self.member, course=self.course)
        enrollment.recalculate_progress()
        self.assertFalse(hasattr(enrollment, "certificate"))
        LessonProgress.objects.create(user=self.member, lesson=self.article_lesson, completed=True)
        LessonProgress.objects.create(user=self.member, lesson=self.video_lesson, completed=True)
        LessonProgress.objects.create(user=self.member, lesson=self.assessment_lesson, completed=True)
        enrollment.recalculate_progress()
        enrollment.refresh_from_db()
        self.assertEqual(enrollment.status, Enrollment.STATUS_COMPLETED)
        self.assertTrue(hasattr(enrollment, "certificate"))

    def test_08_list_my_certificates(self):
        enrollment = Enrollment.objects.create(user=self.member, course=self.course, progress=100,
                                                status=Enrollment.STATUS_COMPLETED)
        cert = Certificate.objects.create(enrollment=enrollment)
        resp = self.client.get("/api/v1/certificates/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        results = resp.data.get("results") or resp.data
        cert_ids = [c["id"] for c in results]
        self.assertIn(str(cert.id), cert_ids)

    def test_09_certificate_detail(self):
        enrollment = Enrollment.objects.create(user=self.member, course=self.course, progress=100,
                                                status=Enrollment.STATUS_COMPLETED)
        cert = Certificate.objects.create(enrollment=enrollment)
        resp = self.client.get(f"/api/v1/certificates/{cert.id}/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_10_certificate_generate_pdf(self):
        enrollment = Enrollment.objects.create(user=self.member, course=self.course, progress=100,
                                                status=Enrollment.STATUS_COMPLETED)
        cert = Certificate.objects.create(enrollment=enrollment)
        resp = self.client.post(f"/api/v1/certificates/{cert.id}/generate-pdf/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        cert.refresh_from_db()
        self.assertTrue(cert.pdf_file)

    def test_11_certificate_download(self):
        enrollment = Enrollment.objects.create(user=self.member, course=self.course, progress=100,
                                                status=Enrollment.STATUS_COMPLETED)
        cert = Certificate.objects.create(enrollment=enrollment)
        cert.pdf_file.save("test.pdf", ContentFile(b"%PDF-1.4 mock"), save=True)
        resp = self.client.get(f"/api/v1/certificates/{cert.id}/download/")
        self.assertIn(resp.status_code, (status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST))

    def test_12_start_assessment(self):
        Enrollment.objects.get_or_create(user=self.member, course=self.course)
        resp = self.client.post(f"/api/v1/assessments/{self.normalized_assessment.id}/start/")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data["status"], "started")

    def test_13_submit_assessment(self):
        Enrollment.objects.get_or_create(user=self.member, course=self.course)
        self.client.post(f"/api/v1/assessments/{self.normalized_assessment.id}/start/")
        submit_resp = self.client.post(f"/api/v1/assessments/{self.normalized_assessment.id}/submit/", {
            "answers": {str(self.question.id): [str(self.correct_choice.id)]}
        }, format="json")
        self.assertEqual(submit_resp.status_code, status.HTTP_200_OK)
        self.assertIn("score", submit_resp.data)
        self.assertIn("passed", submit_resp.data)

    def test_14_resume_assessment(self):
        Enrollment.objects.get_or_create(user=self.member, course=self.course)
        self.client.post(f"/api/v1/assessments/{self.normalized_assessment.id}/start/")
        resp = self.client.get(f"/api/v1/assessments/{self.normalized_assessment.id}/resume/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_15_assessment_history(self):
        Enrollment.objects.get_or_create(user=self.member, course=self.course)
        self.client.post(f"/api/v1/assessments/{self.normalized_assessment.id}/start/")
        resp = self.client.get(f"/api/v1/assessments/{self.normalized_assessment.id}/attempts/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data), 1)

    def test_16_create_training_request(self):
        org = _create_org()
        _create_membership(self.member, org)
        resp = self.client.post("/api/v1/training-requests/", {
            "organization": str(org.id),
            "description": "We need phishing training",
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data["status"], TrainingRequest.STATUS_PENDING)

    def test_17_view_my_notifications(self):
        Notification.objects.create(user=self.member, message="Test notification", type="info")
        resp = self.client.get("/api/v1/notifications/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        results = resp.data.get("results") or resp.data
        self.assertEqual(len(results), 1)

    def test_18_mark_notification_read(self):
        notif = Notification.objects.create(user=self.member, message="Read me", type="info")
        resp = self.client.post(f"/api/v1/notifications/{notif.id}/mark_read/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        notif.refresh_from_db()
        self.assertTrue(notif.is_read)

    def test_19_mark_notification_unread(self):
        notif = Notification.objects.create(user=self.member, message="Unread me", type="info", is_read=True)
        resp = self.client.post(f"/api/v1/notifications/{notif.id}/mark_unread/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        notif.refresh_from_db()
        self.assertFalse(notif.is_read)

    def test_20_acknowledge_alert(self):
        admin = _create_user("alertadmin2@example.com", role=User.ROLE_SUPER_ADMIN)
        alert = Alert.objects.create(title="Important Alert", message="Please read",
                                      severity=Alert.SEVERITY_HIGH, status=Alert.STATUS_PUBLISHED,
                                      created_by=admin)
        resp = self.client.post(f"/api/v1/alerts/{alert.id}/acknowledge/")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

    def test_21_member_cannot_create_course(self):
        resp = self.client.post("/api/v1/courses/", {
            "title": "Member Course",
            "description": "Should fail"
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)


# ---------------------------------------------------------------------------
# 3. ORGANIZATION ADMIN JOURNEY
# ---------------------------------------------------------------------------
class TestOrgAdminJourney(APITestCase):
    """Manage org, members, compliance reports, payment approvals."""

    def setUp(self):
        self.super_admin = _create_user("super@example.com", role=User.ROLE_SUPER_ADMIN, is_staff=True)
        self.org = _create_org(created_by=self.super_admin)
        self.org_admin = _create_user("orgadmin@example.com", role=User.ROLE_ORG_ADMIN)
        _create_membership(self.org_admin, self.org, org_role=OrganizationMembership.ROLE_ADMIN)
        self.client.force_authenticate(self.org_admin)

    def test_01_list_organization_members(self):
        member = _create_user("orgmember@example.com")
        _create_membership(member, self.org)
        resp = self.client.get("/api/v1/memberships/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        results = resp.data.get("results") or resp.data
        self.assertGreaterEqual(len(results), 1)

    def test_02_add_member_to_org(self):
        member = _create_user("newmember@example.com")
        resp = self.client.post("/api/v1/memberships/", {
            "user": str(member.id),
            "organization": str(self.org.id),
            "org_role": OrganizationMembership.ROLE_MEMBER,
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

    def test_03_remove_member(self):
        member = _create_user("removemember@example.com")
        membership = _create_membership(member, self.org)
        resp = self.client.delete(f"/api/v1/memberships/{membership.id}/")
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)

    def test_04_list_compliance_reports(self):
        ComplianceReport.objects.create(organization=self.org, title="Q1 Report",
                                         status=ComplianceReport.STATUS_DRAFT,
                                         report_data={"key": "value"}, created_by=self.org_admin)
        resp = self.client.get("/api/v1/compliance-reports/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        results = resp.data.get("results") or resp.data
        self.assertEqual(len(results), 1)

    def test_05_create_compliance_report(self):
        resp = self.client.post("/api/v1/compliance-reports/", {
            "organization": str(self.org.id),
            "title": "Compliance Report Q2",
            "report_data": {"status": "compliant"},
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

    def test_06_create_payment_approval(self):
        resp = self.client.post("/api/v1/payment-approvals/", {
            "organization": str(self.org.id),
            "amount": "5000.00",
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data["status"], PaymentApproval.STATUS_PENDING)

    def test_07_list_payment_approvals(self):
        PaymentApproval.objects.create(organization=self.org, amount=1000,
                                        created_by=self.org_admin, status=PaymentApproval.STATUS_PENDING)
        resp = self.client.get("/api/v1/payment-approvals/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        results = resp.data.get("results") or resp.data
        self.assertEqual(len(results), 1)

    def test_08_create_campaign(self):
        resp = self.client.post("/api/v1/campaigns/", {
            "title": "Org Campaign",
            "message": "Stay aware!",
            "channels": ["email"],
            "start_date": "2025-06-01",
            "send_time": "10:00:00",
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

    def test_09_org_admin_cannot_create_course(self):
        resp = self.client.post("/api/v1/courses/", {
            "title": "Org Admin Course",
            "description": "Should fail"
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_10_org_admin_cannot_create_organization(self):
        resp = self.client.post("/api/v1/organizations/", {"name": "Rogue Org"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)


# ---------------------------------------------------------------------------
# 4. COURSE PROVIDER JOURNEY
# ---------------------------------------------------------------------------
class TestCourseProviderJourney(APITestCase):
    """Create courses, modules, lessons, articles, videos, assessments."""

    def setUp(self):
        self.provider = _create_user("cp@example.com", role=User.ROLE_COURSE_PROVIDER)
        self.client.force_authenticate(self.provider)

    def test_01_create_course(self):
        resp = self.client.post("/api/v1/courses/", {
            "title": "Cyber Security 101",
            "description": "Intro to security",
            "level": "Beginner",
            "language": "en",
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(str(resp.data["course_provider"]), str(self.provider.id))

    def test_02_list_my_courses(self):
        _create_course(self.provider, title="Course A")
        _create_course(self.provider, title="Course B")
        resp = self.client.get("/api/v1/courses/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        results = resp.data.get("results") or resp.data
        self.assertGreaterEqual(len(results), 2)

    def test_03_update_course(self):
        course = _create_course(self.provider)
        resp = self.client.patch(f"/api/v1/courses/{course.id}/", {"title": "Updated Title"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["title"], "Updated Title")

    def test_04_delete_course(self):
        course = _create_course(self.provider)
        resp = self.client.delete(f"/api/v1/courses/{course.id}/")
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)

    def test_05_create_module(self):
        course = _create_course(self.provider)
        resp = self.client.post("/api/v1/modules/", {
            "course": str(course.id),
            "title": "Module 1",
            "order": 1,
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

    def test_06_create_lesson_article(self):
        course = _create_course(self.provider)
        module = _create_module(course)
        resp = self.client.post("/api/v1/lessons/", {
            "module": str(module.id),
            "title": "Lesson 1",
            "content_type": Lesson.TYPE_ARTICLE,
            "language": "en",
            "content": "This is the lesson content.",
            "order": 1,
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

    def test_07_create_lesson_video(self):
        course = _create_course(self.provider)
        module = _create_module(course)
        resp = self.client.post("/api/v1/lessons/", {
            "module": str(module.id),
            "title": "Video Lesson",
            "content_type": Lesson.TYPE_VIDEO,
            "language": "en",
            "media_url": "https://example.com/video.mp4",
            "order": 1,
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

    def test_08_create_lesson_assessment(self):
        course = _create_course(self.provider)
        module = _create_module(course)
        resp = self.client.post("/api/v1/lessons/", {
            "module": str(module.id),
            "title": "Assessment Lesson",
            "content_type": Lesson.TYPE_ASSESSMENT,
            "language": "en",
            "assessment_type": Lesson.ASSESSMENT_MULTIPLE_CHOICE,
            "assessment_payload": {
                "questions": [{
                    "id": "q1", "type": "multiple_choice", "question": "Pick one?",
                    "correct_answer": "opt1",
                    "options": [{"id": "opt1", "text": "Right"}, {"id": "opt2", "text": "Wrong"}]
                }]
            },
            "passing_score": 70,
            "order": 1,
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertIn("assessment", resp.data)

    def test_09_update_module(self):
        course = _create_course(self.provider)
        module = _create_module(course)
        resp = self.client.patch(f"/api/v1/modules/{module.id}/", {"title": "Updated Module"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["title"], "Updated Module")

    def test_10_delete_module(self):
        course = _create_course(self.provider)
        module = _create_module(course)
        resp = self.client.delete(f"/api/v1/modules/{module.id}/")
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)

    def test_11_create_article(self):
        course = _create_course(self.provider)
        module = _create_module(course)
        resp = self.client.post("/api/v1/articles/", {
            "module": str(module.id),
            "content": "Article content here",
            "order": 1,
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

    def test_12_create_video(self):
        course = _create_course(self.provider)
        module = _create_module(course)
        resp = self.client.post("/api/v1/videos/", {
            "module": str(module.id),
            "video_url": "https://example.com/vid.mp4",
            "duration": 300,
            "order": 1,
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

    def test_13_create_resource(self):
        resp = self.client.post("/api/v1/resources/", {
            "title": "Security Guide",
            "content": "PDF content",
            "category": "pdf",
            "audience": "general",
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data["status"], Resource.STATUS_DRAFT)

    def test_14_update_resource(self):
        resource = Resource.objects.create(title="Draft", content="Content", category="pdf",
                                            audience="general", status=Resource.STATUS_DRAFT,
                                            created_by=self.provider)
        resp = self.client.patch(f"/api/v1/resources/{resource.id}/", {"title": "Updated Resource"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_15_create_certificate_exam(self):
        course = _create_course(self.provider)
        resp = self.client.post("/api/v1/certificate-exams/", {
            "course": str(course.id),
            "title": "Final Exam",
            "passing_score": 70,
            "assessment_type": "multiple",
            "assessment_payload": {
                "questions": [{
                    "id": "ce1", "type": "multiple", "question": "Final Q?",
                    "correct_answer": "c1",
                    "options": [{"id": "c1", "text": "Correct"}, {"id": "c2", "text": "Wrong"}]
                }]
            },
            "order": 1,
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

    def test_16_provider_cannot_assign_organization(self):
        course = _create_course(self.provider)
        org = _create_org()
        resp = self.client.post(f"/api/v1/courses/{course.id}/assign-provider/", {
            "provider_id": str(self.provider.id)
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_17_provider_cannot_create_organization(self):
        resp = self.client.post("/api/v1/organizations/", {"name": "Provider Org"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_18_cannot_update_others_course(self):
        other_provider = _create_user("othercp@example.com", role=User.ROLE_COURSE_PROVIDER)
        course = _create_course(other_provider, title="Not Mine")
        resp = self.client.patch(f"/api/v1/courses/{course.id}/", {"title": "Hacked"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)


# ---------------------------------------------------------------------------
# 5. SUPER ADMIN JOURNEY
# ---------------------------------------------------------------------------
class TestSuperAdminJourney(APITestCase):
    """Full admin: manage users, orgs, alerts, campaigns, resources, analytics, audit, tools."""

    def setUp(self):
        self.admin = _create_user("superadmin@example.com", role=User.ROLE_SUPER_ADMIN, is_staff=True, is_superuser=True)
        self.client.force_authenticate(self.admin)

    def test_01_create_organization(self):
        resp = self.client.post("/api/v1/organizations/", {"name": "Super Org",
                                                             "description": "Created by admin"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

    def test_02_list_organizations(self):
        _create_org("Org 1", created_by=self.admin)
        _create_org("Org 2", created_by=self.admin)
        resp = self.client.get("/api/v1/organizations/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        results = resp.data.get("results") or resp.data
        self.assertGreaterEqual(len(results), 2)

    def test_03_update_organization(self):
        org = _create_org(created_by=self.admin)
        resp = self.client.patch(f"/api/v1/organizations/{org.id}/", {"name": "Updated Org"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_04_delete_organization(self):
        org = _create_org(created_by=self.admin)
        resp = self.client.delete(f"/api/v1/organizations/{org.id}/")
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)

    def test_05_list_org_applications(self):
        OrganizationApplication.objects.create(name="App Org", contact_email="a@b.com",
                                                status=OrganizationApplication.STATUS_PENDING)
        resp = self.client.get("/api/v1/organization-applications/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        results = resp.data.get("results") or resp.data
        self.assertEqual(len(results), 1)

    def test_06_approve_org_application(self):
        app = OrganizationApplication.objects.create(name="New Org", description="Desc",
                                                      contact_email="c@d.com",
                                                      status=OrganizationApplication.STATUS_PENDING)
        resp = self.client.post(f"/api/v1/organization-applications/{app.id}/approve/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        app.refresh_from_db()
        self.assertEqual(app.status, OrganizationApplication.STATUS_APPROVED)
        self.assertTrue(Organization.objects.filter(name="New Org").exists())

    def test_07_reject_org_application(self):
        app = OrganizationApplication.objects.create(name="Bad Org", description="Desc",
                                                      contact_email="e@f.com",
                                                      status=OrganizationApplication.STATUS_PENDING)
        resp = self.client.post(f"/api/v1/organization-applications/{app.id}/reject/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        app.refresh_from_db()
        self.assertEqual(app.status, OrganizationApplication.STATUS_REJECTED)

    def test_08_create_org_admin_user(self):
        org = _create_org(created_by=self.admin)
        resp = self.client.post("/api/auth/users/org-admins/", {
            "email": "neworgadmin@example.com",
            "first_name": "Org",
            "last_name": "Admin",
            "organization_id": str(org.id),
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        user = User.objects.get(email="neworgadmin@example.com")
        self.assertEqual(user.role, User.ROLE_ORG_ADMIN)
        self.assertTrue(user.must_change_password)
        self.assertTrue(OrganizationMembership.objects.filter(user=user, organization=org).exists())

    def test_09_create_course_provider_user(self):
        resp = self.client.post("/api/auth/users/course-providers/", {
            "email": "newcp@example.com",
            "first_name": "Course",
            "last_name": "Provider",
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        user = User.objects.get(email="newcp@example.com")
        self.assertEqual(user.role, User.ROLE_COURSE_PROVIDER)

    def test_10_create_super_admin_user(self):
        resp = self.client.post("/api/auth/users/super-admins/", {
            "email": "newsa@example.com",
            "first_name": "Super",
            "last_name": "Admin",
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        user = User.objects.get(email="newsa@example.com")
        self.assertEqual(user.role, User.ROLE_SUPER_ADMIN)

    def test_11_list_all_users(self):
        _create_user("user1@example.com")
        _create_user("user2@example.com")
        resp = self.client.get("/api/auth/users/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        results = resp.data.get("results") or resp.data
        self.assertGreaterEqual(len(results), 3)

    def test_12_create_alert(self):
        resp = self.client.post("/api/v1/alerts/", {
            "title": "Security Alert",
            "message": "Critical vulnerability detected",
            "severity": Alert.SEVERITY_HIGH,
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

    def test_13_publish_alert(self):
        alert = Alert.objects.create(title="Draft Alert", message="Be aware",
                                      severity=Alert.SEVERITY_MEDIUM,
                                      status=Alert.STATUS_DRAFT, created_by=self.admin)
        resp = self.client.post(f"/api/v1/alerts/{alert.id}/publish/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        alert.refresh_from_db()
        self.assertEqual(alert.status, Alert.STATUS_PUBLISHED)
        self.assertIsNotNone(alert.published_at)

    def test_14_update_alert(self):
        alert = Alert.objects.create(title="Old Title", message="Old", severity=Alert.SEVERITY_LOW,
                                      status=Alert.STATUS_DRAFT, created_by=self.admin)
        resp = self.client.patch(f"/api/v1/alerts/{alert.id}/", {"title": "New Title"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_15_view_alert_deliveries(self):
        alert = Alert.objects.create(title="Deliverable", message="Test", severity=Alert.SEVERITY_LOW,
                                      status=Alert.STATUS_PUBLISHED, created_by=self.admin)
        resp = self.client.get("/api/v1/alert-deliveries/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_16_view_alert_views(self):
        resp = self.client.get("/api/v1/alert-views/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_17_create_campaign(self):
        resp = self.client.post("/api/v1/campaigns/", {
            "title": "Awareness Month",
            "message": "Stay safe online!",
            "channels": ["email", "sms"],
            "start_date": "2025-07-01",
            "send_time": "09:00:00",
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

    def test_18_update_campaign(self):
        campaign = Campaign.objects.create(title="Old Campaign", message="Old", channels=["email"],
                                            start_date="2025-01-01", status=Campaign.STATUS_DRAFT,
                                            created_by=self.admin)
        resp = self.client.patch(f"/api/v1/campaigns/{campaign.id}/", {"title": "Updated Campaign"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_19_delete_campaign(self):
        campaign = Campaign.objects.create(title="Delete Me", message="Bye", channels=["email"],
                                            start_date="2025-01-01", status=Campaign.STATUS_DRAFT,
                                            created_by=self.admin)
        resp = self.client.delete(f"/api/v1/campaigns/{campaign.id}/")
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)

    def test_20_publish_resource(self):
        resource = Resource.objects.create(title="Draft Resource", content="Content", category="pdf",
                                            audience="general", status=Resource.STATUS_DRAFT,
                                            created_by=self.admin)
        resp = self.client.post(f"/api/v1/resources/{resource.id}/publish/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        resource.refresh_from_db()
        self.assertEqual(resource.status, Resource.STATUS_PUBLISHED)

    def test_21_assign_course_provider(self):
        provider = _create_user("assigncp@example.com", role=User.ROLE_COURSE_PROVIDER)
        course = _create_course(provider)
        resp = self.client.post(f"/api/v1/courses/{course.id}/assign-provider/", {
            "provider_id": str(provider.id)
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_22_assign_course_organization(self):
        provider = _create_user("assigncp2@example.com", role=User.ROLE_COURSE_PROVIDER)
        org = _create_org(created_by=self.admin)
        course = _create_course(provider)
        resp = self.client.post(f"/api/v1/courses/{course.id}/assign-organization/", {
            "organization_id": str(org.id)
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_23_create_awareness_tool(self):
        resp = self.client.post("/api/v1/superadmin/awareness-tools/", {
            "name": "Phishing Simulator",
            "description": "Simulate phishing attacks",
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

    def test_24_toggle_awareness_tool(self):
        tool = AwarenessTool.objects.create(name="Toggle Tool", description="Test",
                                             status=AwarenessTool.STATUS_ENABLED, created_by=self.admin)
        resp = self.client.patch(f"/api/v1/superadmin/awareness-tools/{tool.id}/toggle-status/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        tool.refresh_from_db()
        self.assertEqual(tool.status, AwarenessTool.STATUS_DISABLED)

    def test_25_view_awareness_tool_usage(self):
        tool = AwarenessTool.objects.create(name="Usage Tool", description="Test",
                                             status=AwarenessTool.STATUS_ENABLED, created_by=self.admin)
        resp = self.client.get(f"/api/v1/superadmin/awareness-tools/{tool.id}/usage/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_26_view_analytics_dashboard(self):
        resp = self.client.get("/api/v1/analytics/dashboard/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("users", resp.data)
        self.assertIn("courses", resp.data)
        self.assertIn("enrollments", resp.data)
        self.assertIn("certificates", resp.data)
        self.assertIn("assessments", resp.data)
        self.assertIn("alerts", resp.data)

    def test_27_view_audit_logs(self):
        resp = self.client.get("/api/v1/audit-logs/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_28_approve_training_request(self):
        org = _create_org(created_by=self.admin)
        member = _create_user("trainreq@example.com")
        _create_membership(member, org)
        req = TrainingRequest.objects.create(organization=org, created_by=member,
                                              description="Need training",
                                              status=TrainingRequest.STATUS_PENDING)
        resp = self.client.post(f"/api/v1/training-requests/{req.id}/approve/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        req.refresh_from_db()
        self.assertEqual(req.status, TrainingRequest.STATUS_APPROVED)

    def test_29_reject_training_request(self):
        org = _create_org(created_by=self.admin)
        member = _create_user("trainreq2@example.com")
        _create_membership(member, org)
        req = TrainingRequest.objects.create(organization=org, created_by=member,
                                              description="Need training",
                                              status=TrainingRequest.STATUS_PENDING)
        resp = self.client.post(f"/api/v1/training-requests/{req.id}/reject/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        req.refresh_from_db()
        self.assertEqual(req.status, TrainingRequest.STATUS_REJECTED)

    def test_30_approve_payment(self):
        org = _create_org(created_by=self.admin)
        admin_user = _create_user("paymentapprover@example.com", role=User.ROLE_ORG_ADMIN)
        _create_membership(admin_user, org, org_role=OrganizationMembership.ROLE_ADMIN)
        payment = PaymentApproval.objects.create(organization=org, amount=2500,
                                                  created_by=admin_user,
                                                  status=PaymentApproval.STATUS_PENDING)
        resp = self.client.post(f"/api/v1/payment-approvals/{payment.id}/approve/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        payment.refresh_from_db()
        self.assertEqual(payment.status, PaymentApproval.STATUS_APPROVED)

    def test_31_reject_payment(self):
        org = _create_org(created_by=self.admin)
        admin_user = _create_user("paymentrejecter@example.com", role=User.ROLE_ORG_ADMIN)
        _create_membership(admin_user, org, org_role=OrganizationMembership.ROLE_ADMIN)
        payment = PaymentApproval.objects.create(organization=org, amount=1000,
                                                  created_by=admin_user,
                                                  status=PaymentApproval.STATUS_PENDING)
        resp = self.client.post(f"/api/v1/payment-approvals/{payment.id}/reject/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        payment.refresh_from_db()
        self.assertEqual(payment.status, PaymentApproval.STATUS_REJECTED)

    def test_32_delete_user(self):
        user = _create_user("deleteme@example.com")
        resp = self.client.delete(f"/api/auth/users/{user.id}/")
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)

    def test_33_update_user(self):
        user = _create_user("updateme@example.com")
        resp = self.client.patch(f"/api/auth/users/{user.id}/", {"first_name": "Updated"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        user.refresh_from_db()
        self.assertEqual(user.first_name, "Updated")
