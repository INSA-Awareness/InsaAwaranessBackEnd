from django.db import connections
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

from .models import AuditLog
from core.middleware import get_current_user


def _audit_table_exists():
    """Return True if the audit_auditlog table exists in the database."""
    try:
        connection = connections["default"]
        table_names = connection.introspection.table_names()
        return AuditLog._meta.db_table in table_names
    except Exception:
        return False


def _log(instance, action):
    if isinstance(instance, AuditLog):
        return
    if not _audit_table_exists():
        return
    actor = get_current_user()
    if actor is None:
        actor = getattr(instance, "updated_by", None) or getattr(instance, "created_by", None)
    AuditLog.objects.create(
        actor=actor,
        action=action,
        app_label=instance._meta.app_label,
        model=instance._meta.model_name,
        object_id=str(getattr(instance, "pk", "")),
        changes={},
    )


@receiver(post_save)
def log_save(sender, instance, created, **kwargs):
    if sender._meta.app_label == "sessions":
        return
    _log(instance, "create" if created else "update")


@receiver(post_delete)
def log_delete(sender, instance, **kwargs):
    if sender._meta.app_label == "sessions":
        return
    _log(instance, "delete")
