import uuid

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from core.models import SoftDeleteModel

User = settings.AUTH_USER_MODEL


class Course(SoftDeleteModel):
    STATUS_DRAFT = "draft"
    STATUS_PUBLISHED = "published"
    STATUS_ARCHIVED = "archived"
    STATUS_CHOICES = [
        (STATUS_DRAFT, "Draft"),
        (STATUS_PUBLISHED, "Published"),
        (STATUS_ARCHIVED, "Archived"),
    ]

    LANGUAGE_CHOICES = [
        ("en", "English"),
        ("am", "Amharic"),
        ("om", "Afaan Oromo"),
        ("ti", "Tigrinya"),
        ("so", "Somali"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    level = models.CharField(max_length=100, blank=True)
    course_provider = models.ForeignKey(User, related_name="courses_provided", on_delete=models.PROTECT)
    organization = models.ForeignKey(
        "organizations.Organization",
        related_name="courses",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    created_by = models.ForeignKey(User, related_name="courses_created", on_delete=models.SET_NULL, null=True)
    assigned_by = models.ForeignKey(User, related_name="courses_assigned", on_delete=models.SET_NULL, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    language = models.CharField(max_length=10, choices=LANGUAGE_CHOICES, default="en")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title


class Module(SoftDeleteModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    course = models.ForeignKey(Course, related_name="modules", on_delete=models.CASCADE)
    title = models.CharField(max_length=255)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order"]

    def __str__(self):
        return f"{self.course}: {self.title}"


class Article(SoftDeleteModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    module = models.ForeignKey(Module, related_name="articles", on_delete=models.CASCADE)
    content = models.TextField()
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order"]


class Video(SoftDeleteModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    module = models.ForeignKey(Module, related_name="videos", on_delete=models.CASCADE)
    video_url = models.URLField()
    duration = models.PositiveIntegerField(default=0)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order"]


class Assessment(SoftDeleteModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    module = models.ForeignKey(Module, related_name="assessments", on_delete=models.CASCADE)
    title = models.CharField(max_length=255)
    passing_score = models.PositiveIntegerField(default=0)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order"]


class Enrollment(SoftDeleteModel):
    STATUS_IN_PROGRESS = "in_progress"
    STATUS_COMPLETED = "completed"
    STATUS_CHOICES = [
        (STATUS_IN_PROGRESS, "In Progress"),
        (STATUS_COMPLETED, "Completed"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, related_name="enrollments", on_delete=models.CASCADE)
    course = models.ForeignKey(Course, related_name="enrollments", on_delete=models.CASCADE)
    progress = models.PositiveIntegerField(default=0, validators=[MinValueValidator(0), MaxValueValidator(100)])
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_IN_PROGRESS)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("user", "course")


class Lesson(SoftDeleteModel):
    TYPE_VIDEO = "video"
    TYPE_ARTICLE = "article"
    TYPE_IMAGE = "image"
    TYPE_ASSESSMENT = "assessment"
    TYPE_CHOICES = [
        (TYPE_VIDEO, "Video"),
        (TYPE_ARTICLE, "Article"),
        (TYPE_IMAGE, "Image"),
        (TYPE_ASSESSMENT, "Assessment"),
    ]

    ASSESSMENT_TRUE_FALSE = "true_false"
    ASSESSMENT_MULTIPLE_CHOICE = "multiple_choice"
    ASSESSMENT_MATCHING = "matching"
    ASSESSMENT_CHOICES = [
        (ASSESSMENT_TRUE_FALSE, "True/False"),
        (ASSESSMENT_MULTIPLE_CHOICE, "Multiple Choice"),
        (ASSESSMENT_MATCHING, "Matching"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    module = models.ForeignKey(Module, related_name="lessons", on_delete=models.CASCADE)
    title = models.CharField(max_length=255)
    content_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    language = models.CharField(max_length=10, choices=Course.LANGUAGE_CHOICES, default="en")
    content = models.TextField(blank=True)
    media_url = models.URLField(blank=True)
    image_url = models.URLField(blank=True)
    assessment_type = models.CharField(max_length=30, choices=ASSESSMENT_CHOICES, blank=True)
    assessment_payload = models.JSONField(default=dict, blank=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order"]


class Certificate(SoftDeleteModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    enrollment = models.OneToOneField(Enrollment, related_name="certificate", on_delete=models.CASCADE)
    certificate_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    issued_at = models.DateTimeField(auto_now_add=True)


class EnrollmentProfileSnapshot(SoftDeleteModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    enrollment = models.OneToOneField(Enrollment, related_name="profile_snapshot", on_delete=models.CASCADE)
    user = models.ForeignKey(User, related_name="enrollment_snapshots", on_delete=models.CASCADE)
    course = models.ForeignKey(Course, related_name="enrollment_snapshots", on_delete=models.CASCADE)

    nationality = models.CharField(max_length=32, blank=True)
    region = models.CharField(max_length=64, blank=True)
    age_range = models.CharField(max_length=16, blank=True)
    phone_number = models.CharField(max_length=32, blank=True)
    gender = models.CharField(max_length=16, blank=True)
    education_level = models.CharField(max_length=32, blank=True)
    field_of_study = models.CharField(max_length=32, blank=True)
    institution_name = models.CharField(max_length=255, blank=True)
    employment_status = models.CharField(max_length=32, blank=True)
    employer_name = models.CharField(max_length=255, blank=True)
    unemployment_description = models.TextField(blank=True)
    professional_experience = models.CharField(max_length=16, blank=True)
    enrollment_motivation = models.CharField(max_length=32, blank=True)
    referral_source = models.CharField(max_length=32, blank=True)
    is_information_confirmed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]