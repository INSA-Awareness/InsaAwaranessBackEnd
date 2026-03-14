from django.shortcuts import render
from django.http import HttpRequest, HttpResponse
from django.utils import timezone
from django.views.generic import TemplateView
from django.conf import settings


class HealthView(TemplateView):
    template_name = "health.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update({
            "now": timezone.now().isoformat(),
            "debug": settings.DEBUG,
        })
        return ctx


def custom_404(request: HttpRequest, exception=None) -> HttpResponse:
    return render(request, "404.html", status=404)
