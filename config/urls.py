from urllib.parse import quote

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path, re_path
from django.views.decorators.clickjacking import xframe_options_exempt
from django.views.generic import RedirectView
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from django.views.static import serve

from apps.payments.views import StripeWebhookView


def health(request):
    return JsonResponse(
        {"status": "ok", "service": "backend"},
        headers={"Cache-Control": "no-store"},
    )


def serve_media(request, path, document_root=None, **kwargs):
    """Wraps django.views.static.serve to (1) declare UTF-8 for text files --
    without it browsers guess the charset (often wrong) for uploaded .txt/.md
    materials, garbling any non-ASCII (e.g. Cyrillic) content -- and (2) force
    a real "Save As" download when the frontend's Download button links here
    with `?download=<name>`, instead of just opening the file in a new tab.
    Plain links (used by the in-app image/PDF/text preview) are untouched, so
    those keep rendering inline."""
    response = serve(request, path, document_root=document_root, **kwargs)
    content_type = response.get("Content-Type", "")
    if content_type.startswith("text/") and "charset=" not in content_type:
        response["Content-Type"] = f"{content_type}; charset=utf-8"

    download_name = request.GET.get("download")
    if download_name:
        response["Content-Disposition"] = f"attachment; filename*=UTF-8''{quote(download_name)}"
    return response


urlpatterns = [
    path("", RedirectView.as_view(url="/api/v1/", permanent=False)),
    path("health", health, name="health"),
    path("webhook", StripeWebhookView.as_view(), name="stripe-webhook-root"),
    path("webhook/", StripeWebhookView.as_view(), name="stripe-webhook-root-slash"),
    path("admin/", admin.site.urls),
    path("api/v1/", include("apps.users.urls")),
    path("api/v1/", include("apps.courses.urls")),
    path("api/v1/", include("apps.schedule.urls")),
    path("api/v1/", include("apps.cart.urls")),
    path("api/v1/", include("apps.curriculum.urls")),
    path("api/v1/", include("apps.enrollments.urls")),
    path("api/v1/", include("apps.certificates.urls")),
    path("api/v1/", include("apps.homework.urls")),
    path("api/v1/", include("apps.notifications.urls")),
    path("api/v1/", include("apps.chat.urls")),
    path("api/v1/", include("apps.payments.urls")),
    path("api/v1/", include("apps.reviews.urls")),
    path("api/v1/", include("apps.blog.urls")),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
]

if settings.DEBUG:
    urlpatterns += [
        # Exempt from X-Frame-Options: media files (PDFs, images...) are previewed
        # in an <iframe> by the frontend, which the default DENY would block.
        re_path(r"^media/(?P<path>.*)$", xframe_options_exempt(serve_media), {"document_root": settings.MEDIA_ROOT}),
    ]
