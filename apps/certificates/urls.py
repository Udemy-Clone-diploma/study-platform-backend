from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.certificates.views import CertificateVerifyView, CertificateViewSet

router = DefaultRouter()
router.register(r"certificates", CertificateViewSet, basename="certificates")

urlpatterns = [
    # Must precede the router include: the router's detail route
    # (`certificates/<pk>/`) would otherwise swallow `certificates/verify/<x>/`
    # by treating "verify" as a pk.
    path(
        "certificates/verify/<str:lookup>/",
        CertificateVerifyView.as_view(),
        name="certificate-verify",
    ),
    path("", include(router.urls)),
]
