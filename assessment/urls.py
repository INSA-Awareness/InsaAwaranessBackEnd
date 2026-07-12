from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import AssessmentViewSet, QuestionViewSet, ChoiceViewSet

router = DefaultRouter()
router.register(r"assessments", AssessmentViewSet, basename="assessment")
router.register(r"assessment-questions", QuestionViewSet, basename="assessment-question")
router.register(r"assessment-choices", ChoiceViewSet, basename="assessment-choice")

urlpatterns = [
    path("", include(router.urls)),
]
