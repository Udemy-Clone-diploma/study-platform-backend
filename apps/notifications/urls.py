from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.notifications.views import NotificationPreferenceView, NotificationViewSet

router = DefaultRouter()
router.register(r"notifications", NotificationViewSet, basename="notifications")

urlpatterns = [
    # Registered before the router so it is not captured by the `{pk}` detail route.
    path(
        "notifications/preferences/",
        NotificationPreferenceView.as_view(),
        name="notification-preferences",
    ),
    path("", include(router.urls)),
]
