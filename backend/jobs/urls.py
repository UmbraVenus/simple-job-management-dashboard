"""URLs of the jobs API: ``jobs/`` and ``jobs/<id>/``."""
from rest_framework.routers import SimpleRouter

from jobs.views import JobViewSet

# SimpleRouter, not DefaultRouter: no extra "API root" page.
router = SimpleRouter()
router.register("jobs", JobViewSet, basename="job")

urlpatterns = router.urls
