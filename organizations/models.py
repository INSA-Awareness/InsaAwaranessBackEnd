import uuid

from django.conf import settings
from django.db import models

from core.models import SoftDeleteModel

User = settings.AUTH_USER_MODEL


class Organization(SoftDeleteModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True)
    created_by = models.ForeignKey(User, related_name="organizations_created", on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class OrganizationApplication(SoftDeleteModel):
    STATUS_PENDING = "pending"
    STATUS_APPROVED = "approved"
    STATUS_REJECTED = "rejected"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_APPROVED, "Approved"),
        (STATUS_REJECTED, "Rejected"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    description = models.TextField()
    contact_email = models.EmailField()
    contact_phone = models.CharField(max_length=64)
    website = models.URLField(blank=True)
    address = models.CharField(max_length=255)
    submitted_by = models.ForeignKey(User, related_name="org_applications", on_delete=models.SET_NULL, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    reviewed_by = models.ForeignKey(User, related_name="org_applications_reviewed", on_delete=models.SET_NULL, null=True, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        unique_together = ("name", "contact_email")

    def __str__(self):
        return f"Application: {self.name} ({self.status})"


class OrganizationMembership(SoftDeleteModel):
    ROLE_ADMIN = "admin"
    ROLE_MEMBER = "member"
    ROLE_CHOICES = [(ROLE_ADMIN, "Admin"), (ROLE_MEMBER, "Member")]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, related_name="memberships", on_delete=models.CASCADE)
    organization = models.ForeignKey(Organization, related_name="members", on_delete=models.CASCADE)
    org_role = models.CharField(max_length=10, choices=ROLE_CHOICES, default=ROLE_MEMBER)
    department = models.CharField(max_length=255, blank=True)
    employee_id = models.CharField(max_length=100, blank=True)
    is_primary = models.BooleanField(default=False)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "organization")

    def __str__(self):
        return f"{self.user} -> {self.organization} ({self.org_role})"