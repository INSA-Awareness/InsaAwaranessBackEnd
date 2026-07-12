from __future__ import annotations

from collections.abc import Iterable

from django.db import transaction
from django.utils import timezone

from assessment.models import Assessment, AssessmentAttempt, AssessmentAnswer, Choice, MatchingPair, OrderingItem, Question


LEGACY_TO_NEW_QUESTION_TYPES = {
    "multiple": Question.TYPE_MULTIPLE_CHOICE,
    "multiple_choice": Question.TYPE_MULTIPLE_CHOICE,
    "multiple_select": Question.TYPE_MULTIPLE_SELECT,
    "true_false": Question.TYPE_TRUE_FALSE,
    "matching": Question.TYPE_MATCHING,
}

NEW_TO_LEGACY_QUESTION_TYPES = {
    Question.TYPE_MULTIPLE_CHOICE: "multiple_choice",
    Question.TYPE_MULTIPLE_SELECT: "multiple_select",
    Question.TYPE_TRUE_FALSE: "true_false",
    Question.TYPE_FILL_BLANK: "fill_blank",
    Question.TYPE_MATCHING: "matching",
    Question.TYPE_ORDERING: "ordering",
    Question.TYPE_SHORT_ANSWER: "short_answer",
    Question.TYPE_ESSAY: "essay",
}


def _normalize_text(value):
    if value is None:
        return ""
    return str(value).strip()


def _choice_text(option):
    if not isinstance(option, dict):
        return str(option)
    for key in ("text", "label", "value", "answer", "title"):
        if option.get(key) not in [None, ""]:
            return str(option[key])
    return str(option.get("id", ""))


def _clear_assessment_children(assessment: Assessment):
    assessment.questions.all().hard_delete()


@transaction.atomic
def sync_assessment_from_legacy_payload(assessment: Assessment, payload: dict | None):
    payload = payload or {}
    questions = payload.get("questions") or []
    _clear_assessment_children(assessment)
    for index, question_payload in enumerate(questions, start=1):
        if not isinstance(question_payload, dict):
            continue
        question_type = LEGACY_TO_NEW_QUESTION_TYPES.get(question_payload.get("type"), Question.TYPE_MULTIPLE_CHOICE)
        question = Question.objects.create(
            assessment=assessment,
            type=question_type,
            prompt=_normalize_text(question_payload.get("question")),
            explanation=_normalize_text(question_payload.get("explanation")),
            order=int(question_payload.get("order") or index),
            points=int(question_payload.get("points") or 1),
            is_required=bool(question_payload.get("is_required", True)),
            allow_multiple_selection=bool(question_payload.get("allow_multiple_selection", False)),
            case_sensitive=bool(question_payload.get("case_sensitive", False)),
            correct_text_answer=_normalize_text(question_payload.get("correct_answer"))
            if question_type in {Question.TYPE_FILL_BLANK, Question.TYPE_SHORT_ANSWER}
            else "",
        )

        if question_type in {Question.TYPE_MULTIPLE_CHOICE, Question.TYPE_MULTIPLE_SELECT, Question.TYPE_TRUE_FALSE}:
            options = question_payload.get("options") or []
            if question_type == Question.TYPE_TRUE_FALSE and not options:
                options = [
                    {"id": True, "text": "True"},
                    {"id": False, "text": "False"},
                ]
            correct_answer = question_payload.get("correct_answer")
            if question_type == Question.TYPE_MULTIPLE_SELECT and not isinstance(correct_answer, list):
                correct_answer = [correct_answer] if correct_answer not in [None, ""] else []
            for option_index, option in enumerate(options, start=1):
                option_id = option.get("id") if isinstance(option, dict) else None
                Choice.objects.create(
                    question=question,
                    text=_choice_text(option),
                    value=str(option_id) if option_id not in [None, ""] else "",
                    is_correct=(option_id in correct_answer) if isinstance(correct_answer, list) else option_id == correct_answer,
                    order=int(option.get("order") or option_index) if isinstance(option, dict) else option_index,
                )
        elif question_type == Question.TYPE_MATCHING:
            pairs = question_payload.get("correct_answer") or {}
            if isinstance(pairs, dict):
                for pair_index, (left_text, right_text) in enumerate(pairs.items(), start=1):
                    MatchingPair.objects.create(
                        question=question,
                        left_text=_normalize_text(left_text),
                        right_text=_normalize_text(right_text),
                        order=pair_index,
                    )
        elif question_type == Question.TYPE_ORDERING:
            items = question_payload.get("items") or []
            for item_index, item in enumerate(items, start=1):
                OrderingItem.objects.create(
                    question=question,
                    text=_choice_text(item),
                    order=int(item.get("order") or item_index) if isinstance(item, dict) else item_index,
                )
    return assessment


def assessment_to_legacy_payload(assessment: Assessment) -> dict:
    questions = []
    for question in assessment.questions.prefetch_related("choices", "matching_pairs", "ordering_items").all().order_by("order", "created_at"):
        question_payload = {
            "id": str(question.id),
            "type": NEW_TO_LEGACY_QUESTION_TYPES.get(question.type, question.type),
            "question": question.prompt,
            "correct_answer": question.correct_text_answer,
            "order": question.order,
            "points": question.points,
            "is_required": question.is_required,
        }
        if question.type in {Question.TYPE_MULTIPLE_CHOICE, Question.TYPE_MULTIPLE_SELECT, Question.TYPE_TRUE_FALSE}:
            choices = []
            for choice in question.choices.all():
                choices.append(
                    {
                        "id": str(choice.id),
                        "text": choice.text,
                        "value": choice.value,
                        "is_correct": choice.is_correct,
                        "order": choice.order,
                    }
                )
            question_payload["options"] = choices
            correct_choice_ids = [str(choice.id) for choice in question.choices.filter(is_correct=True)]
            if question.type == Question.TYPE_MULTIPLE_SELECT:
                question_payload["correct_answer"] = correct_choice_ids
            elif question.type == Question.TYPE_TRUE_FALSE:
                question_payload["correct_answer"] = bool(correct_choice_ids and question.choices.filter(is_correct=True).first().text.lower() in {"true", "1", "yes"})
            else:
                question_payload["correct_answer"] = correct_choice_ids[0] if correct_choice_ids else None
        elif question.type == Question.TYPE_MATCHING:
            question_payload["correct_answer"] = {pair.left_text: pair.right_text for pair in question.matching_pairs.all()}
        elif question.type == Question.TYPE_ORDERING:
            question_payload["items"] = [
                {"id": str(item.id), "text": item.text, "order": item.order}
                for item in question.ordering_items.all()
            ]
            question_payload["correct_answer"] = [str(item.id) for item in question.ordering_items.all().order_by("order", "created_at")]
        questions.append(question_payload)
    return {"questions": questions}


def _extract_selected_choice_ids(response_data):
    choice_ids = response_data.get("choice_ids")
    if isinstance(choice_ids, list):
        return [str(choice_id) for choice_id in choice_ids if choice_id not in [None, ""]]
    selected_choice_id = response_data.get("choice_id")
    if selected_choice_id not in [None, ""]:
        return [str(selected_choice_id)]
    return []


@transaction.atomic
def save_attempt_response(attempt: AssessmentAttempt, question: Question, response_data: dict):
    answer, _ = AssessmentAnswer.objects.get_or_create(attempt=attempt, question=question)
    answer.response_json = response_data or {}
    answer.response_text = _normalize_text(response_data.get("text")) if isinstance(response_data, dict) else ""
    answer.requires_manual_grading = question.requires_manual_grading
    answer.save()
    choice_ids = _extract_selected_choice_ids(response_data or {}) if isinstance(response_data, dict) else []
    if choice_ids:
        selected_choices = list(question.choices.filter(id__in=choice_ids))
        answer.selected_choices.set(selected_choices)
    else:
        answer.selected_choices.clear()
    return answer


def _normalize_answer_text(value, case_sensitive=False):
    normalized = _normalize_text(value)
    return normalized if case_sensitive else normalized.lower()


@transaction.atomic
def grade_attempt(attempt: AssessmentAttempt):
    questions = list(attempt.assessment.questions.prefetch_related("choices", "matching_pairs", "ordering_items").all().order_by("order", "created_at"))
    answers = {answer.question_id: answer for answer in attempt.answers.all()}
    max_score = 0.0
    score = 0.0
    manual_review_required = False

    for question in questions:
        max_score += float(question.points)
        answer = answers.get(question.id)
        if not answer:
            continue

        answer.requires_manual_grading = question.requires_manual_grading
        if question.requires_manual_grading:
            answer.is_correct = None
            manual_review_required = True
            answer.save(update_fields=["requires_manual_grading", "is_correct", "updated_at"])
            continue

        is_correct = False
        response_data = answer.response_json or {}

        if question.type in {Question.TYPE_MULTIPLE_CHOICE, Question.TYPE_MULTIPLE_SELECT, Question.TYPE_TRUE_FALSE}:
            selected_ids = {str(choice_id) for choice_id in answer.selected_choices.values_list("id", flat=True)}
            correct_ids = {str(choice_id) for choice_id in question.choices.filter(is_correct=True).values_list("id", flat=True)}
            if question.type == Question.TYPE_MULTIPLE_SELECT:
                is_correct = selected_ids == correct_ids and bool(selected_ids)
            else:
                is_correct = len(selected_ids) == 1 and selected_ids == correct_ids
        elif question.type == Question.TYPE_FILL_BLANK:
            submitted = _normalize_answer_text(response_data.get("text") or answer.response_text, question.case_sensitive)
            expected = _normalize_answer_text(question.correct_text_answer, question.case_sensitive)
            is_correct = submitted == expected and expected != ""
        elif question.type == Question.TYPE_MATCHING:
            submitted_pairs = response_data.get("pairs") if isinstance(response_data, dict) else None
            if isinstance(submitted_pairs, dict):
                expected = {pair.left_text: pair.right_text for pair in question.matching_pairs.all()}
                normalized_submitted = {str(left): str(right) for left, right in submitted_pairs.items()}
                is_correct = normalized_submitted == expected and bool(expected)
        elif question.type == Question.TYPE_ORDERING:
            submitted_order = response_data.get("order") if isinstance(response_data, dict) else None
            if isinstance(submitted_order, list):
                expected_order = [str(item.id) for item in question.ordering_items.all().order_by("order", "created_at")]
                is_correct = [str(item_id) for item_id in submitted_order] == expected_order and bool(expected_order)

        answer.is_correct = is_correct
        answer.score = float(question.points) if is_correct else 0.0
        score += answer.score
        answer.save(update_fields=["requires_manual_grading", "is_correct", "score", "updated_at"])

    percentage_score = (score / max_score) * 100 if max_score else 0.0
    attempt.max_score = max_score
    attempt.score = percentage_score
    attempt.passed = max_score > 0 and percentage_score >= float(attempt.assessment.passing_score)
    attempt.status = AssessmentAttempt.STATUS_GRADED if not manual_review_required else AssessmentAttempt.STATUS_NEEDS_REVIEW
    attempt.graded_at = timezone.now()
    attempt.save(update_fields=["max_score", "score", "passed", "status", "graded_at", "updated_at"])
    return attempt
