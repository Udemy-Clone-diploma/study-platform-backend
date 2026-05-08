import uuid
from pathlib import Path

from django.utils.deconstruct import deconstructible
from rest_framework.request import Request


def absolute_media_url(field_file, request: Request | None) -> str | None:
    if not field_file:
        return None
    url = field_file.url
    return request.build_absolute_uri(url) if request else url


@deconstructible
class UUIDUploadTo:
    """ImageField/FileField upload_to that stores files under <prefix>/<uuid>.<ext>.

    Keeps URLs unique across replacements so CDN caches stay correct
    regardless of the storage backend's overwrite policy.
    """

    def __init__(self, prefix: str):
        self.prefix = prefix.rstrip("/")

    def __call__(self, instance, filename: str) -> str:
        suffix = Path(filename).suffix.lower()
        return f"{self.prefix}/{uuid.uuid4().hex}{suffix}"

    def __eq__(self, other):
        return isinstance(other, UUIDUploadTo) and self.prefix == other.prefix
