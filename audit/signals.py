""" from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

from .models import AuditLog


def _log(instance, action):
    if isinstance(instance, AuditLog):
        return
    AuditLog.objects.create(
        actor=getattr(instance, "updated_by", None) or getattr(instance, "created_by", None),
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
    _log(instance, "delete") """