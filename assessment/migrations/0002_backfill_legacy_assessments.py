from django.db import migrations, transaction


LEGACY_TO_NEW_QUESTION_TYPES = {
    "multiple": "multiple_choice",
    "multiple_choice": "multiple_choice",
    "multiple_select": "multiple_select",
    "true_false": "true_false",
    "matching": "matching",
    "ordering": "ordering",
    "fill_blank": "fill_blank",
    "short_answer": "short_answer",
    "essay": "essay",
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


@transaction.atomic
def forwards(apps, schema_editor):
    LegacyLesson = apps.get_model("courses", "Lesson")
    LegacyAssessment = apps.get_model("courses", "Assessment")
    Assessment = apps.get_model("assessment", "Assessment")
    Question = apps.get_model("assessment", "Question")
    Choice = apps.get_model("assessment", "Choice")
    MatchingPair = apps.get_model("assessment", "MatchingPair")
    OrderingItem = apps.get_model("assessment", "OrderingItem")

    for lesson in LegacyLesson.objects.filter(content_type="assessment"):
        payload = lesson.assessment_payload or {}
        assessment, _ = Assessment.objects.get_or_create(
            lesson=lesson,
            defaults={
                "title": lesson.title,
                "passing_score": lesson.passing_score,
            },
        )
        assessment.title = lesson.title
        assessment.passing_score = lesson.passing_score
        assessment.save(update_fields=["title", "passing_score", "updated_at"])

        assessment.questions.all().delete()
        questions = payload.get("questions") or []
        for index, question_payload in enumerate(questions, start=1):
            if not isinstance(question_payload, dict):
                continue
            question_type = LEGACY_TO_NEW_QUESTION_TYPES.get(question_payload.get("type"), "multiple_choice")
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
                if question_type in {"fill_blank", "short_answer"}
                else "",
            )

            if question_type in {"multiple_choice", "multiple_select", "true_false"}:
                options = question_payload.get("options") or []
                if question_type == "true_false" and not options:
                    options = [
                        {"id": True, "text": "True"},
                        {"id": False, "text": "False"},
                    ]
                correct_answer = question_payload.get("correct_answer")
                if question_type == "multiple_select" and not isinstance(correct_answer, list):
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
            elif question_type == "matching":
                pairs = question_payload.get("correct_answer") or {}
                if isinstance(pairs, dict):
                    for pair_index, (left_text, right_text) in enumerate(pairs.items(), start=1):
                        MatchingPair.objects.create(
                            question=question,
                            left_text=_normalize_text(left_text),
                            right_text=_normalize_text(right_text),
                            order=pair_index,
                        )
            elif question_type == "ordering":
                items = question_payload.get("items") or []
                for item_index, item in enumerate(items, start=1):
                    OrderingItem.objects.create(
                        question=question,
                        text=_choice_text(item),
                        order=int(item.get("order") or item_index) if isinstance(item, dict) else item_index,
                    )

    for exam in LegacyAssessment.objects.all():
        payload = exam.assessment_payload or {}
        assessment, _ = Assessment.objects.get_or_create(
            certificate_exam=exam,
            defaults={
                "title": exam.title,
                "passing_score": exam.passing_score,
            },
        )
        assessment.title = exam.title
        assessment.passing_score = exam.passing_score
        assessment.save(update_fields=["title", "passing_score", "updated_at"])

        assessment.questions.all().delete()
        questions = payload.get("questions") or []
        for index, question_payload in enumerate(questions, start=1):
            if not isinstance(question_payload, dict):
                continue
            question_type = LEGACY_TO_NEW_QUESTION_TYPES.get(question_payload.get("type"), "multiple_choice")
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
                if question_type in {"fill_blank", "short_answer"}
                else "",
            )

            if question_type in {"multiple_choice", "multiple_select", "true_false"}:
                options = question_payload.get("options") or []
                if question_type == "true_false" and not options:
                    options = [
                        {"id": True, "text": "True"},
                        {"id": False, "text": "False"},
                    ]
                correct_answer = question_payload.get("correct_answer")
                if question_type == "multiple_select" and not isinstance(correct_answer, list):
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
            elif question_type == "matching":
                pairs = question_payload.get("correct_answer") or {}
                if isinstance(pairs, dict):
                    for pair_index, (left_text, right_text) in enumerate(pairs.items(), start=1):
                        MatchingPair.objects.create(
                            question=question,
                            left_text=_normalize_text(left_text),
                            right_text=_normalize_text(right_text),
                            order=pair_index,
                        )
            elif question_type == "ordering":
                items = question_payload.get("items") or []
                for item_index, item in enumerate(items, start=1):
                    OrderingItem.objects.create(
                        question=question,
                        text=_choice_text(item),
                        order=int(item.get("order") or item_index) if isinstance(item, dict) else item_index,
                    )


def backwards(apps, schema_editor):
    return None


class Migration(migrations.Migration):
    dependencies = [
        ("assessment", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
