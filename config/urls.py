import mimetypes
import posixpath
import re
from pathlib import Path
from urllib.parse import quote

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.http import FileResponse, HttpResponse, JsonResponse
from django.urls import include, path, re_path
from django.utils._os import safe_join
from django.views.decorators.clickjacking import xframe_options_exempt
from django.views.generic import RedirectView
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from django.views.static import serve

from apps.payments.views import StripeWebhookView
from apps.common.cache import cache_is_available


def health(request):
    cache_available = cache_is_available()
    return JsonResponse(
        {
            "status": "ok" if cache_available else "degraded",
            "service": "backend",
            "components": {
                "cache": "ok" if cache_available else "unavailable",
            },
        },
        headers={"Cache-Control": "no-store"},
    )


_RANGE_RE = re.compile(r"bytes=(\d*)-(\d*)$")


class _LimitedReader:
    """Wraps a file handle already seeked to the range start, stopping reads
    after `length` bytes. Deliberately exposes only read()/close() (no
    seek/tell/name), FileResponse.set_headers() only auto-computes
    Content-Length from those attributes, and here that would overwrite the
    single-range Content-Length this view sets explicitly."""

    def __init__(self, fileobj, length):
        self._fileobj = fileobj
        self._remaining = length

    def read(self, size=-1):
        if self._remaining <= 0:
            self.close()
            return b""
        if size < 0 or size > self._remaining:
            size = self._remaining
        data = self._fileobj.read(size)
        self._remaining -= len(data)
        if not data or self._remaining <= 0:
            self.close()
        return data

    def close(self):
        self._fileobj.close()


def _serve_media_range(path, document_root, range_header):
    """A single-range 206 response, so <video>/<audio> scrubbing works.

    django.views.static.serve (which serve_media wraps below) always returns
    the whole file with a plain 200, it never implements HTTP Range at all
    (confirmed: there is no Range/Content-Range handling anywhere in Django's
    own source). Without this, the browser has no way to seek without first
    downloading the entire file, so it just disables the scrubber outright for
    any reasonably large video.

    Returns None (falls back to the normal full-file response) for a missing
    file or a Range header this doesn't understand, multi-range requests
    ("bytes=0-99,200-299") aren't supported, which is fine: browsers doing
    video seeking only ever send a single range.
    """
    match = _RANGE_RE.match(range_header.strip())
    if not match:
        return None

    normalized = posixpath.normpath(path).lstrip("/")
    fullpath = Path(safe_join(document_root, normalized))
    if not fullpath.is_file():
        return None

    file_size = fullpath.stat().st_size
    start_s, end_s = match.groups()
    if start_s:
        start = int(start_s)
        end = int(end_s) if end_s else file_size - 1
    elif end_s:
        # Suffix form, "bytes=-500" = the last 500 bytes.
        start = max(file_size - int(end_s), 0)
        end = file_size - 1
    else:
        return None
    end = min(end, file_size - 1)

    if start >= file_size or start > end:
        response = HttpResponse(status=416)
        response["Content-Range"] = f"bytes */{file_size}"
        return response

    length = end - start + 1
    content_type, encoding = mimetypes.guess_type(str(fullpath))
    content_type = content_type or "application/octet-stream"

    file_obj = fullpath.open("rb")
    file_obj.seek(start)
    response = FileResponse(
        _LimitedReader(file_obj, length),
        status=206,
        content_type=content_type,
    )
    if encoding:
        response.headers["Content-Encoding"] = encoding
    response["Content-Length"] = str(length)
    response["Content-Range"] = f"bytes {start}-{end}/{file_size}"
    response["Accept-Ranges"] = "bytes"
    return response


def serve_media(request, path, document_root=None, **kwargs):
    """Wraps django.views.static.serve to (1) answer HTTP Range requests with
    a real 206 (see _serve_media_range), (2) declare UTF-8 for text files,
    without it browsers guess the charset (often wrong) for uploaded .txt/.md
    materials, garbling any non-ASCII (e.g. Cyrillic) content, and (3) force
    a real "Save As" download when the frontend's Download button links here
    with `?download=<name>`, instead of just opening the file in a new tab.
    Plain links (used by the in-app image/PDF/text preview) are untouched, so
    those keep rendering inline."""
    range_header = request.META.get("HTTP_RANGE")
    if range_header:
        ranged_response = _serve_media_range(path, document_root, range_header)
        if ranged_response is not None:
            return ranged_response

    response = serve(request, path, document_root=document_root, **kwargs)
    response["Accept-Ranges"] = "bytes"
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
