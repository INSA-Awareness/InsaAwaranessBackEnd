import uuid

from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.db import models

from core.models import SoftDeleteModel, SoftDeleteManager


class SoftDeleteUserManager(SoftDeleteManager, BaseUserManager):
    def _create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("Email must be set")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        extra_fields.setdefault("role", "member")
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("role", "super_admin")
        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")
        return self._create_user(email, password, **extra_fields)


class User(SoftDeleteModel, AbstractBaseUser, PermissionsMixin):
    ROLE_SUPER_ADMIN = "super_admin"
    ROLE_ORG_ADMIN = "org_admin"
    ROLE_COURSE_PROVIDER = "course_provider"
    ROLE_MEMBER = "member"
    ROLE_PUBLIC = "public_user"

    ROLE_CHOICES = [
        (ROLE_SUPER_ADMIN, "Super Admin"),
        (ROLE_ORG_ADMIN, "Org Admin"),
        (ROLE_COURSE_PROVIDER, "Course Provider"),
        (ROLE_MEMBER, "Member"),
        (ROLE_PUBLIC, "Public User"),
    ]

    LANGUAGE_CHOICES = [
        ("en", "English"),
        ("am", "Amharic"),
        ("om", "Afaan Oromo"),
        ("ti", "Tigrinya"),
        ("so", "Somali"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=150, blank=True)
    last_name = models.CharField(max_length=150, blank=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=ROLE_MEMBER)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(auto_now_add=True)
    preferred_language = models.CharField(max_length=10, choices=LANGUAGE_CHOICES, default="en")
    must_change_password = models.BooleanField(default=False)
    created_by = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="users_created",
    )

    objects = SoftDeleteUserManager()
    all_objects = SoftDeleteUserManager(include_deleted=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS: list[str] = []

    class Meta:
        ordering = ["-date_joined"]

    def __str__(self):
        return self.email

    @property
    def primary_organization(self):
        primary = self.memberships.filter(is_primary=True).first()
        return primary.organization if primary else None

    @property
    def dashboard_route(self) -> str:
        match self.role:
            case self.ROLE_SUPER_ADMIN:
                return "/dashboard/super-admin"
            case self.ROLE_ORG_ADMIN:
                return "/dashboard/organization"
            case self.ROLE_COURSE_PROVIDER:
                return "/dashboard/course-provider"
            case self.ROLE_MEMBER:
                return "/dashboard/member"
            case _:
                return "/dashboard/public"

    @property
    def is_public_user(self) -> bool:
        return self.role == self.ROLE_PUBLIC


class BackgroundProfile(SoftDeleteModel):
    NATIONALITY_ETHIOPIA = "ethiopia"
    NATIONALITY_KENYA = "kenya"
    NATIONALITY_RWANDA = "rwanda"
    NATIONALITY_UGANDA = "uganda"
    NATIONALITY_OTHER = "other"
    NATIONALITY_CHOICES = [
        (NATIONALITY_ETHIOPIA, "Ethiopia"),
        (NATIONALITY_KENYA, "Kenya"),
        (NATIONALITY_RWANDA, "Rwanda"),
        (NATIONALITY_UGANDA, "Uganda"),
        (NATIONALITY_OTHER, "Other"),
    ]

    REGION_CHOICES = [
        ("addis_ababa", "Addis Ababa"),
        ("amhara", "Amhara Region"),
        ("afar", "Afar Region"),
        ("benishangul_gumuz", "Benishangul-Gumuz"),
        ("central_ethiopia", "Central Ethiopia"),
        ("dire_dawa", "Dire Dawa"),
        ("gambela", "Gambela"),
        ("harari", "Harari"),
        ("oromia", "Oromia"),
        ("sidama", "Sidama"),
        ("somali", "Somali"),
        ("south_ethiopia", "South Ethiopia"),
        ("southwest_ethiopia", "Southwest Ethiopia People's Region"),
        ("tigray", "Tigray"),
    ]

    AGE_RANGE_CHOICES = [
        ("13_17", "13–17"),
        ("18_22", "18–22"),
        ("23_25", "23–25"),
        ("26_30", "26–30"),
        ("31_35", "31–35"),
        ("36_40", "36–40"),
        ("41_plus", "41 and Older"),
    ]

    GENDER_CHOICES = [("male", "Male"), ("female", "Female")]

    EDUCATION_LEVEL_CHOICES = [
        ("high_school", "High School"),
        ("bachelor", "Bachelor's Degree"),
        ("master", "Master's Degree"),
        ("phd", "PhD"),
        ("other", "Other"),
    ]

    FIELD_OF_STUDY_CHOICES = [
        ("agriculture", "Agriculture"),
        ("arts", "Arts"),
        ("business", "Business"),
        ("cs_it", "Computer science and IT"),
        ("education", "Education"),
        ("engineering", "Engineering"),
        ("humanities", "Humanities"),
        ("law", "Law"),
        ("medicine", "Medicine"),
        ("natural_science", "Natural science"),
        ("social_science", "Social science"),
        ("other", "Other"),
    ]

    EMPLOYMENT_STATUS_CHOICES = [
        ("full_time", "Full-time employee"),
        ("part_time", "Part-time employee"),
        ("freelancer", "Freelancer"),
        ("entrepreneur", "Entrepreneur"),
        ("student", "Student"),
        ("unemployed", "Unemployed"),
        ("other", "Other"),
    ]

    EXPERIENCE_CHOICES = [
        ("none", "No professional experience"),
        ("lt_1", "<1 year"),
        ("1_2", "1–2 years"),
        ("2_3", "2–3 years"),
        ("3_5", "3–5 years"),
        ("5_6", "5–6 years"),
        ("6_10", "6–10 years"),
        ("10_plus", "10+ years"),
    ]

    MOTIVATION_CHOICES = [
        ("new_job", "Start a new job"),
        ("promotion", "Get promotion or raise"),
        ("new_skill", "Learn new skill"),
        ("advanced_degree", "Prepare for advanced degree"),
        ("start_business", "Start business"),
        ("interest", "General interest"),
        ("internship", "Internship preparation"),
        ("other", "Other"),
    ]

    REFERRAL_CHOICES = [
        ("email", "Email"),
        ("linkedin", "LinkedIn"),
        ("facebook", "Facebook"),
        ("instagram", "Instagram"),
        ("twitter", "Twitter"),
        ("telegram", "Telegram"),
        ("search_engine", "Search Engine"),
        ("sms", "SMS"),
        ("website_search", "Website search"),
        ("program_website", "Program website"),
        ("friend_referral", "Friend referral"),
        ("other", "Other"),
    ]

    user = models.OneToOneField(User, related_name="background_profile", on_delete=models.CASCADE)
    nationality = models.CharField(max_length=32, choices=NATIONALITY_CHOICES, blank=True)
    region = models.CharField(max_length=64, choices=REGION_CHOICES, blank=True)
    age_range = models.CharField(max_length=16, choices=AGE_RANGE_CHOICES, blank=True)
    phone_number = models.CharField(max_length=32, blank=True)
    gender = models.CharField(max_length=16, choices=GENDER_CHOICES, blank=True)
    education_level = models.CharField(max_length=32, choices=EDUCATION_LEVEL_CHOICES, blank=True)
    field_of_study = models.CharField(max_length=32, choices=FIELD_OF_STUDY_CHOICES, blank=True)
    institution_name = models.CharField(max_length=255, blank=True)
    employment_status = models.CharField(max_length=32, choices=EMPLOYMENT_STATUS_CHOICES, blank=True)
    employer_name = models.CharField(max_length=255, blank=True)
    unemployment_description = models.TextField(blank=True)
    professional_experience = models.CharField(max_length=16, choices=EXPERIENCE_CHOICES, blank=True)
    enrollment_motivation = models.CharField(max_length=32, choices=MOTIVATION_CHOICES, blank=True)
    referral_source = models.CharField(max_length=32, choices=REFERRAL_CHOICES, blank=True)
    is_information_confirmed = models.BooleanField(default=False)

    class Meta:
        ordering = ["user__email"]

    def __str__(self):
        return f"BackgroundProfile({self.user.email})"

    def is_complete(self) -> bool:
        required = [
            self.nationality,
            self.age_range,
            self.phone_number,
            self.gender,
            self.education_level,
            self.field_of_study,
            self.employment_status,
            self.professional_experience,
            self.enrollment_motivation,
            self.referral_source,
        ]
        if not all(required):
            return False
        if self.nationality == self.NATIONALITY_ETHIOPIA and not self.region:
            return False
        if self.employment_status in {"unemployed", "other"} and not self.unemployment_description:
            return False
        if not self.is_information_confirmed:
            return False
        return True