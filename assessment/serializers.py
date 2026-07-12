from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import serializers

from .models import Assessment, AssessmentAttempt, AssessmentAnswer, Choice, MatchingPair, OrderingItem, Question
from .services import assessment_to_legacy_payload, grade_attempt, save_attempt_response, sync_assessment_from_legacy_payload

User = get_user_model()


class ChoiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Choice
        fields = ["id", "question", "text", "value", "is_correct", "order", "created_at"]
        read_only_fields = ["id", "created_at"]


class MatchingPairSerializer(serializers.ModelSerializer):
    class Meta:
        model = MatchingPair
        fields = ["id", "question", "left_text", "right_text", "order", "created_at"]
        read_only_fields = ["id", "created_at"]


class OrderingItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderingItem
        fields = ["id", "question", "text", "order", "created_at"]
        read_only_fields = ["id", "created_at"]


class QuestionSerializer(serializers.ModelSerializer):
    choices = ChoiceSerializer(many=True, read_only=True)
    matching_pairs = MatchingPairSerializer(many=True, read_only=True)
    ordering_items = OrderingItemSerializer(many=True, read_only=True)
    requires_manual_grading = serializers.BooleanField(read_only=True)

    class Meta:
        model = Question
        fields = [
            "id",
            "assessment",
            "type",
            "prompt",
            "explanation",
            "order",
            "points",
            "is_required",
            "allow_multiple_selection",
            "case_sensitive",
            "correct_text_answer",
            "requires_manual_grading",
            "choices",
            "matching_pairs",
            "ordering_items",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "requires_manual_grading", "created_at", "updated_at"]


class AssessmentSerializer(serializers.ModelSerializer):
    questions = QuestionSerializer(many=True, read_only=True)
    assessment_payload = serializers.SerializerMethodField()
    legacy_assessment_payload = serializers.JSONField(write_only=True, required=False, allow_null=True)
    parent_type = serializers.CharField(read_only=True)

    class Meta:
        model = Assessment
        fields = [
            "id",
            "lesson",
            "certificate_exam",
            "parent_type",
            "title",
            "description",
            "passing_score",
            "time_limit_minutes",
            "shuffle_questions",
            "assessment_payload",
            "legacy_assessment_payload",
            "questions",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "parent_type", "assessment_payload", "questions", "created_at", "updated_at"]

    def get_assessment_payload(self, instance):
        return assessment_to_legacy_payload(instance)

    def create(self, validated_data):
        payload = validated_data.pop("legacy_assessment_payload", None)
        assessment = Assessment.objects.create(**validated_data)
        if payload not in [None, ""]:
            sync_assessment_from_legacy_payload(assessment, payload)
        return assessment

    def update(self, instance, validated_data):
        payload = validated_data.pop("legacy_assessment_payload", None)
        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.save()
        if payload not in [None, ""]:
            sync_assessment_from_legacy_payload(instance, payload)
        return instance


class AssessmentAnswerSerializer(serializers.ModelSerializer):
    selected_choice_ids = serializers.ListField(child=serializers.UUIDField(), write_only=True, required=False)

    class Meta:
        model = AssessmentAnswer
        fields = [
            "id",
            "attempt",
            "question",
            "selected_choice_ids",
            "response_text",
            "response_json",
            "is_correct",
            "requires_manual_grading",
            "score",
            "graded_by",
            "graded_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "is_correct", "requires_manual_grading", "score", "graded_by", "graded_at", "created_at", "updated_at"]

    def create(self, validated_data):
        selected_choice_ids = validated_data.pop("selected_choice_ids", [])
        answer = AssessmentAnswer.objects.create(**validated_data)
        if selected_choice_ids:
            answer.selected_choices.set(Choice.objects.filter(id__in=selected_choice_ids))
        return answer

    def update(self, instance, validated_data):
        selected_choice_ids = validated_data.pop("selected_choice_ids", None)
        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.save()
        if selected_choice_ids is not None:
            instance.selected_choices.set(Choice.objects.filter(id__in=selected_choice_ids))
        return instance


class AssessmentAttemptSerializer(serializers.ModelSerializer):
    answers = AssessmentAnswerSerializer(many=True, read_only=True)

    class Meta:
        model = AssessmentAttempt
        fields = [
            "id",
            "assessment",
            "user",
            "attempt_number",
            "status",
            "score",
            "max_score",
            "passed",
            "current_question_index",
            "started_at",
            "last_saved_at",
            "submitted_at",
            "graded_at",
            "answers",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "status",
            "score",
            "max_score",
            "passed",
            "started_at",
            "last_saved_at",
            "submitted_at",
            "graded_at",
            "answers",
            "created_at",
            "updated_at",
        ]


class AssessmentAttemptActionSerializer(serializers.Serializer):
    question_id = serializers.UUIDField(required=False)
    answer = serializers.JSONField(required=False)
    current_question_index = serializers.IntegerField(required=False, min_value=0)
    answers = serializers.DictField(child=serializers.JSONField(), required=False)

    def save(self, **kwargs):
        attempt = self.context["attempt"]
        question_id = self.validated_data.get("question_id")
        answer_data = self.validated_data.get("answer")
        current_question_index = self.validated_data.get("current_question_index")
        answers = self.validated_data.get("answers")

        if current_question_index is not None:
            attempt.current_question_index = current_question_index
            attempt.status = AssessmentAttempt.STATUS_IN_PROGRESS
            attempt.save(update_fields=["current_question_index", "status", "updated_at"])

        if question_id is not None and answer_data is not None:
            question = attempt.assessment.questions.get(id=question_id)
            if isinstance(answer_data, list):
                payload = {"choice_ids": answer_data}
            elif isinstance(answer_data, dict):
                payload = answer_data
            else:
                payload = {"text": answer_data}
            save_attempt_response(attempt, question, payload)
            attempt.status = AssessmentAttempt.STATUS_IN_PROGRESS
            attempt.save(update_fields=["status", "updated_at"])

        if isinstance(answers, dict):
            for key, value in answers.items():
                question = attempt.assessment.questions.get(id=key)
                if isinstance(value, list):
                    payload = {"choice_ids": value}
                elif isinstance(value, dict):
                    payload = value
                else:
                    payload = {"text": value}
                save_attempt_response(attempt, question, payload)
            attempt.status = AssessmentAttempt.STATUS_IN_PROGRESS
            attempt.save(update_fields=["status", "updated_at"])

        return attempt


class AssessmentSubmissionSerializer(serializers.Serializer):
    answers = serializers.DictField(child=serializers.JSONField(), required=False)

    def save(self, **kwargs):
        attempt = self.context["attempt"]
        answers = self.validated_data.get("answers") or {}
        for question_id, response_data in answers.items():
            question = attempt.assessment.questions.get(id=question_id)
            if isinstance(response_data, list):
                payload = {"choice_ids": response_data}
            elif isinstance(response_data, dict):
                payload = response_data
            else:
                payload = {"text": response_data}
            save_attempt_response(attempt, question, payload)
        attempt.status = AssessmentAttempt.STATUS_SUBMITTED
        attempt.submitted_at = timezone.now()
        attempt.save(update_fields=["status", "submitted_at", "updated_at"])
        return grade_attempt(attempt)


class LegacyAssessmentBridgeSerializer(serializers.Serializer):
    assessment_payload = serializers.JSONField(required=False)

    def save(self, **kwargs):
        assessment = self.context["assessment"]
        payload = self.validated_data.get("assessment_payload") or {}
        return sync_assessment_from_legacy_payload(assessment, payload)
