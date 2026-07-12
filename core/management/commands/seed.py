from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

from organizations.models import Organization, OrganizationMembership
from courses.models import Course, Module, Article, Video, Assessment as CourseAssessment, Enrollment, Lesson
from campaigns.models import Campaign
from resources.models import Resource
from finance.models import PaymentApproval
from training_requests.models import TrainingRequest
from assessment.models import Assessment, Question, Choice


class Command(BaseCommand):
    help = "Seed database with sample data"

    def handle(self, *args, **options):
        User = get_user_model()

        super_admin, _ = User.objects.get_or_create(
            email="super@example.com",
            defaults={"first_name": "Super", "last_name": "Admin", "role": "super_admin", "is_staff": True, "is_superuser": True},
        )
        super_admin.set_password("password123")
        super_admin.save()

        org_admin, _ = User.objects.get_or_create(
            email="orgadmin@example.com",
            defaults={"first_name": "Org", "last_name": "Admin", "role": "org_admin"},
        )
        org_admin.set_password("password123")
        org_admin.save()

        course_provider, _ = User.objects.get_or_create(
            email="provider@example.com",
            defaults={"first_name": "Course", "last_name": "Provider", "role": "course_provider"},
        )
        course_provider.set_password("password123")
        course_provider.save()

        member, _ = User.objects.get_or_create(
            email="member@example.com",
            defaults={"first_name": "Member", "last_name": "User", "role": "member"},
        )
        member.set_password("password123")
        member.save()

        org, _ = Organization.objects.get_or_create(name="Acme Corp", defaults={"description": "Seed org", "created_by": super_admin})

        OrganizationMembership.objects.get_or_create(user=org_admin, organization=org, defaults={"org_role": "admin", "is_primary": True})
        OrganizationMembership.objects.get_or_create(user=member, organization=org, defaults={"org_role": "member", "is_primary": True})
        OrganizationMembership.objects.get_or_create(user=course_provider, organization=org, defaults={"org_role": "member", "is_primary": True})

        course, _ = Course.objects.get_or_create(
            title="Security Awareness",
            defaults={
                "description": "Intro course",
                "level": "Beginner",
                "organization": org,
                "created_by": course_provider,
                "status": Course.STATUS_PUBLISHED,
                "is_active": True,
            },
        )

        mod1, _ = Module.objects.get_or_create(course=course, order=1, defaults={"title": "Introduction"})
        Article.objects.get_or_create(module=mod1, order=1, defaults={"content": "Welcome"})
        Video.objects.get_or_create(module=mod1, order=2, defaults={"video_url": "https://example.com/video", "duration": 120})
        lesson = Lesson.objects.get_or_create(
            module=mod1,
            title="Introduction Quiz",
            defaults={
                "content_type": Lesson.TYPE_ASSESSMENT,
                "language": "en",
                "assessment_type": Lesson.ASSESSMENT_MULTIPLE_CHOICE,
                "assessment_payload": {
                    "questions": [
                        {
                            "id": "q1",
                            "type": "multiple_choice",
                            "question": "What is phishing?",
                            "correct_answer": "c1",
                            "options": [
                                {"id": "c1", "text": "A fraudulent attempt to obtain sensitive information"},
                                {"id": "c2", "text": "A security protocol"},
                            ],
                        }
                    ]
                },
                "passing_score": 70,
            },
        )[0]

        lesson_assessment, _ = Assessment.objects.get_or_create(
            lesson=lesson,
            defaults={"title": lesson.title, "passing_score": 70},
        )
        question, _ = Question.objects.get_or_create(
            assessment=lesson_assessment,
            order=1,
            defaults={"type": Question.TYPE_MULTIPLE_CHOICE, "prompt": "What is phishing?", "points": 1},
        )
        Choice.objects.get_or_create(question=question, order=1, defaults={"text": "A fraudulent attempt to obtain sensitive information", "value": "c1", "is_correct": True})
        Choice.objects.get_or_create(question=question, order=2, defaults={"text": "A security protocol", "value": "c2", "is_correct": False})

        CourseAssessment.objects.get_or_create(course=course, order=3, defaults={"title": "Quiz", "passing_score": 70})

        Enrollment.objects.get_or_create(user=member, course=course, defaults={"progress": 0})

        Campaign.objects.get_or_create(title="Launch Campaign", defaults={"organization": org, "created_by": super_admin, "status": "draft"})

        Resource.objects.get_or_create(title="Policy", defaults={"organization": org, "content": "Policy doc", "created_by": course_provider})

        PaymentApproval.objects.get_or_create(organization=org, amount=1000, defaults={"created_by": org_admin})

        TrainingRequest.objects.get_or_create(organization=org, created_by=member, defaults={"description": "Need training"})

        self.stdout.write(self.style.SUCCESS("Seed data created."))