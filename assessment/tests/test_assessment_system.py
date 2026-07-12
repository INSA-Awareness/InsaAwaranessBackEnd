from django.urls import reverse
from rest_framework.test import APITestCase

from accounts.models import User
from assessment.models import Assessment, Choice, Question
from assessment.services import assessment_to_legacy_payload, sync_assessment_from_legacy_payload
from courses.models import Course, Lesson, Module
from courses.serializers import LessonSerializer


class AssessmentSystemTests(APITestCase):
    def setUp(self):
        self.provider = User.objects.create_user(
            email="provider@example.com",
            password="password123",
            role=User.ROLE_COURSE_PROVIDER,
        )
        self.course = Course.objects.create(
            title="Cyber Safety",
            description="Intro course",
            thumbnail_url="",
            level="Beginner",
            course_provider=self.provider,
            created_by=self.provider,
            status=Course.STATUS_PUBLISHED,
            language="en",
            is_active=True,
        )
        self.module = Module.objects.create(course=self.course, title="Module 1", order=1)
        self.lesson = Lesson.objects.create(
            module=self.module,
            title="Assessment Lesson",
            content_type=Lesson.TYPE_ASSESSMENT,
            language="en",
            assessment_type=Lesson.ASSESSMENT_MULTIPLE_CHOICE,
            assessment_payload={},
            passing_score=70,
            order=1,
        )
        self.assessment = Assessment.objects.create(lesson=self.lesson, title="Assessment Lesson", passing_score=70)
        self.question = Question.objects.create(
            assessment=self.assessment,
            type=Question.TYPE_MULTIPLE_CHOICE,
            prompt="Which password is strongest?",
            order=1,
            points=5,
        )
        self.correct_choice = Choice.objects.create(
            question=self.question,
            text="A long random passphrase",
            value="strong",
            is_correct=True,
            order=1,
        )
        Choice.objects.create(
            question=self.question,
            text="123456",
            value="weak",
            is_correct=False,
            order=2,
        )
        self.client.force_authenticate(self.provider)

    def test_legacy_payload_sync_creates_normalized_graph(self):
        payload = {
            "questions": [
                {
                    "id": "q1",
                    "type": "multiple_choice",
                    "question": "Pick the safe option",
                    "correct_answer": "a1",
                    "options": [
                        {"id": "a1", "text": "Use MFA"},
                        {"id": "a2", "text": "Reuse passwords"},
                    ],
                },
                {
                    "id": "q2",
                    "type": "matching",
                    "question": "Match the term",
                    "correct_answer": {"phishing": "fraud", "mfa": "security"},
                },
            ]
        }
        sync_assessment_from_legacy_payload(self.assessment, payload)
        self.assertEqual(self.assessment.questions.count(), 2)
        first_question = self.assessment.questions.get(order=1)
        self.assertEqual(first_question.choices.count(), 2)
        serialized = assessment_to_legacy_payload(self.assessment)
        self.assertEqual(len(serialized["questions"]), 2)
        self.assertEqual(serialized["questions"][0]["correct_answer"], str(first_question.choices.get(is_correct=True).id))

    def test_assessment_attempt_submit_grades_and_history(self):
        start_response = self.client.post(reverse("assessment-start", args=[self.assessment.id]), format="json")
        self.assertEqual(start_response.status_code, 201)
        self.assertEqual(str(start_response.data["assessment"]), str(self.assessment.id))

        submit_response = self.client.post(
            reverse("assessment-submit", args=[self.assessment.id]),
            {
                "answers": {
                    str(self.question.id): {"choice_ids": [str(self.correct_choice.id)]},
                }
            },
            format="json",
        )
        self.assertEqual(submit_response.status_code, 200)
        self.assertEqual(submit_response.data["score"], 100.0)
        self.assertTrue(submit_response.data["passed"])
        self.assertEqual(submit_response.data["status"], "graded")

        history_response = self.client.get(reverse("assessment-attempts", args=[self.assessment.id]))
        self.assertEqual(history_response.status_code, 200)
        self.assertEqual(len(history_response.data), 1)
        self.assertEqual(history_response.data[0]["status"], "graded")

    def test_lesson_serializer_exposes_related_assessment(self):
        data = LessonSerializer(self.lesson, context={"request": None}).data
        self.assertIn("assessment", data)
        self.assertIsNotNone(data["assessment"])
        self.assertEqual(data["assessment"]["id"], str(self.assessment.id))
        self.assertIn("questions", data["assessment"])
