import uuid

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q

from core.models import SoftDeleteModel

User = settings.AUTH_USER_MODEL


class Assessment(SoftDeleteModel):
    PARENT_LESSON = "lesson"
    PARENT_CERTIFICATE_EXAM = "certificate_exam"
    PARENT_CHOICES = [
        (PARENT_LESSON, "Lesson"),
        (PARENT_CERTIFICATE_EXAM, "Certificate Exam"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    lesson = models.OneToOneField(
        "courses.Lesson",
        related_name="assessment",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
    )
    certificate_exam = models.OneToOneField(
        "courses.Assessment",
        related_name="assessment",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
    )
    title = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True)
    passing_score = models.PositiveIntegerField(default=0, validators=[MinValueValidator(0), MaxValueValidator(100)])
    time_limit_minutes = models.PositiveIntegerField(default=0)
    shuffle_questions = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=(Q(lesson__isnull=False) & Q(certificate_exam__isnull=True))
                | (Q(lesson__isnull=True) & Q(certificate_exam__isnull=False)),
                name="assessment_exactly_one_parent",
            )
        ]

    def __str__(self):
        return self.title or str(self.pk)

    @property
    def parent_type(self):
        if self.lesson_id:
            return self.PARENT_LESSON
        if self.certificate_exam_id:
            return self.PARENT_CERTIFICATE_EXAM
        return None

    @property
    def parent(self):
        return self.lesson or self.certificate_exam


class Question(SoftDeleteModel):
    TYPE_MULTIPLE_CHOICE = "multiple_choice"
    TYPE_MULTIPLE_SELECT = "multiple_select"
    TYPE_TRUE_FALSE = "true_false"
    TYPE_FILL_BLANK = "fill_blank"
    TYPE_MATCHING = "matching"
    TYPE_ORDERING = "ordering"
    TYPE_SHORT_ANSWER = "short_answer"
    TYPE_ESSAY = "essay"

    TYPE_CHOICES = [
        (TYPE_MULTIPLE_CHOICE, "Multiple Choice"),
        (TYPE_MULTIPLE_SELECT, "Multiple Select"),
        (TYPE_TRUE_FALSE, "True/False"),
        (TYPE_FILL_BLANK, "Fill in the Blank"),
        (TYPE_MATCHING, "Matching"),
        (TYPE_ORDERING, "Ordering"),
        (TYPE_SHORT_ANSWER, "Short Answer"),
        (TYPE_ESSAY, "Essay"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    assessment = models.ForeignKey(Assessment, related_name="questions", on_delete=models.CASCADE)
    type = models.CharField(max_length=32, choices=TYPE_CHOICES)
    prompt = models.TextField()
    explanation = models.TextField(blank=True)
    order = models.PositiveIntegerField(default=0)
    points = models.PositiveIntegerField(default=1)
    is_required = models.BooleanField(default=True)
    allow_multiple_selection = models.BooleanField(default=False)
    case_sensitive = models.BooleanField(default=False)
    correct_text_answer = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["order", "created_at"]
        unique_together = ("assessment", "order")

    def __str__(self):
        return self.prompt[:80]

    @property
    def requires_manual_grading(self):
        return self.type in {self.TYPE_SHORT_ANSWER, self.TYPE_ESSAY}


class Choice(SoftDeleteModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    question = models.ForeignKey(Question, related_name="choices", on_delete=models.CASCADE)
    text = models.CharField(max_length=255)
    value = models.CharField(max_length=255, blank=True)
    is_correct = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["order", "created_at"]
        unique_together = ("question", "order")

    def __str__(self):
        return self.text


class MatchingPair(SoftDeleteModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    question = models.ForeignKey(Question, related_name="matching_pairs", on_delete=models.CASCADE)
    left_text = models.CharField(max_length=255)
    right_text = models.CharField(max_length=255)
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["order", "created_at"]
        unique_together = ("question", "order")


class OrderingItem(SoftDeleteModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    question = models.ForeignKey(Question, related_name="ordering_items", on_delete=models.CASCADE)
    text = models.CharField(max_length=255)
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["order", "created_at"]
        unique_together = ("question", "order")


class AssessmentAttempt(SoftDeleteModel):
    STATUS_STARTED = "started"
    STATUS_IN_PROGRESS = "in_progress"
    STATUS_SUBMITTED = "submitted"
    STATUS_GRADED = "graded"
    STATUS_NEEDS_REVIEW = "needs_review"

    STATUS_CHOICES = [
        (STATUS_STARTED, "Started"),
        (STATUS_IN_PROGRESS, "In Progress"),
        (STATUS_SUBMITTED, "Submitted"),
        (STATUS_GRADED, "Graded"),
        (STATUS_NEEDS_REVIEW, "Needs Review"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    assessment = models.ForeignKey(Assessment, related_name="attempts", on_delete=models.CASCADE)
    user = models.ForeignKey(User, related_name="assessment_attempts_v2", on_delete=models.CASCADE)
    attempt_number = models.PositiveIntegerField(default=1)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_STARTED)
    score = models.FloatField(default=0)
    max_score = models.FloatField(default=0)
    passed = models.BooleanField(default=False)
    current_question_index = models.PositiveIntegerField(default=0)
    started_at = models.DateTimeField(auto_now_add=True)
    last_saved_at = models.DateTimeField(auto_now=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    graded_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        unique_together = ("assessment", "user", "attempt_number")

    def __str__(self):
        return f"{self.assessment_id} / {self.user_id} / #{self.attempt_number}"


class AssessmentAnswer(SoftDeleteModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    attempt = models.ForeignKey(AssessmentAttempt, related_name="answers", on_delete=models.CASCADE)
    question = models.ForeignKey(Question, related_name="answers", on_delete=models.CASCADE)
    selected_choices = models.ManyToManyField(Choice, blank=True, related_name="assessment_answers")
    response_text = models.TextField(blank=True)
    response_json = models.JSONField(default=dict, blank=True)
    is_correct = models.BooleanField(null=True, blank=True)
    requires_manual_grading = models.BooleanField(default=False)
    score = models.FloatField(default=0)
    graded_by = models.ForeignKey(User, null=True, blank=True, related_name="graded_assessment_answers", on_delete=models.SET_NULL)
    graded_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["created_at"]
        unique_together = ("attempt", "question")

    def __str__(self):
        return f"Answer {self.attempt_id} / {self.question_id}"
