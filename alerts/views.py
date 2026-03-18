from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework import viewsets, permissions, decorators, response, status
from django.core.mail import EmailMultiAlternatives

from core.permissions import IsSuperAdmin
from .models import Alert, AlertDelivery, AlertView
from .serializers import AlertSerializer, AlertDeliverySerializer, AlertViewSerializer

User = get_user_model()


class AlertViewSet(viewsets.ModelViewSet):
    queryset = Alert.objects.select_related("organization", "created_by")
    serializer_class = AlertSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_permissions(self):
        if self.action in ["create", "update", "partial_update", "destroy", "publish"]:
            return [IsSuperAdmin()]
        if self.action in ["list", "retrieve", "acknowledge"]:
            return [permissions.AllowAny()]
        return super().get_permissions()

    def get_queryset(self):
        qs = super().get_queryset()
        severity = self.request.query_params.get("severity")
        if severity:
            qs = qs.filter(severity=severity)

        user = self.request.user
        if not user.is_authenticated:
            return qs.filter(status=Alert.STATUS_PUBLISHED)
        if getattr(user, "role", None) == "super_admin":
            return qs
        return qs.filter(Q(status=Alert.STATUS_PUBLISHED) | Q(created_by=user))

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @decorators.action(detail=True, methods=["post"], permission_classes=[IsSuperAdmin])
    def publish(self, request, pk=None):
        alert = self.get_object()
        alert.publish()
        self._send_notifications(alert)
        return response.Response({"detail": "Alert published"})

    @decorators.action(detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated])
    def acknowledge(self, request, pk=None):
        alert = self.get_object()
        AlertView.objects.get_or_create(alert=alert, user=request.user)
        return response.Response({"detail": "Acknowledged"}, status=status.HTTP_201_CREATED)

    def _send_notifications(self, alert: Alert):
        recipients = User.objects.filter(is_active=True)
        if alert.organization_id:
            recipients = recipients.filter(memberships__organization_id=alert.organization_id)

        # Send emails
        if alert.notify_email:
            for user in recipients.iterator():
                delivery = AlertDelivery.objects.create(
                    alert=alert,
                    user=user,
                    channel=AlertDelivery.CHANNEL_EMAIL,
                    status=AlertDelivery.STATUS_PENDING,
                )
                try:
                    subject = f"Security Alert: {alert.title} ({alert.severity.title()})"
                    text_body = f"{alert.message}\n\nSeverity: {alert.severity.title()}"
                    html_body = f"""
                    <div style="font-family:Arial,sans-serif;line-height:1.6;color:#111">
                      <h2 style=\"margin:0 0 12px 0;color:#b91c1c\">Security Alert ({alert.severity.title()})</h2>
                      <p style=\"margin:0 0 12px 0\">{alert.message}</p>
                      <p style=\"margin:0 0 12px 0;font-size:12px;color:#555\">If you have questions, contact your administrator.</p>
                    </div>
                    """
                    msg = EmailMultiAlternatives(subject=subject, body=text_body, to=[user.email])
                    msg.attach_alternative(html_body, "text/html")
                    msg.send(fail_silently=False)
                    delivery.status = AlertDelivery.STATUS_SENT
                    delivery.delivered_at = timezone.now()
                except Exception as exc:  # noqa: BLE001
                    delivery.status = AlertDelivery.STATUS_FAILED
                    delivery.detail = str(exc)
                delivery.save(update_fields=["status", "delivered_at", "detail"])

        # Log SMS intent if enabled (placeholder)
        if alert.notify_sms:
            now = timezone.now()
            deliveries = [
                AlertDelivery(
                    alert=alert,
                    user=user,
                    channel=AlertDelivery.CHANNEL_SMS,
                    status=AlertDelivery.STATUS_PENDING,
                    detail="SMS delivery not implemented; integrate provider",
                    delivered_at=None,
                )
                for user in recipients.iterator()
            ]
            AlertDelivery.objects.bulk_create(deliveries, batch_size=500)


class AlertDeliveryViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = AlertDelivery.objects.select_related("alert", "user", "alert__organization")
    serializer_class = AlertDeliverySerializer
    permission_classes = [IsSuperAdmin]


class AlertViewLogViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = AlertView.objects.select_related("alert", "user", "alert__organization")
    serializer_class = AlertViewSerializer
    permission_classes = [IsSuperAdmin]
