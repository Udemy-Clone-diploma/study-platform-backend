import hashlib
import uuid
from pathlib import Path

from django.core.files.base import ContentFile
from django.utils.deconstruct import deconstructible
from rest_framework.request import Request


def absolute_media_url(field_file, request: Request | None) -> str | None:
    if not field_file:
        return None
    url = field_file.url
    return request.build_absolute_uri(url) if request else url


def file_content_hash(field_file) -> str | None:
    """MD5 of a FileField's bytes, or None if it's empty/missing from storage"""
    if not field_file:
        return None
    if not field_file.storage.exists(field_file.name):
        return None
    field_file.open("rb")
    try:
        return hashlib.md5(field_file.read()).hexdigest()
    finally:
        field_file.close()


def duplicate_file_field(source_field, target_field) -> None:
    """Physically copy a FileField's bytes onto another instance's field, under a
    freshly generated storage path """
    if not source_field:
        return
    if not source_field.storage.exists(source_field.name):
        return
    source_field.open("rb")
    try:
        content = source_field.read()
    finally:
        source_field.close()
    target_field.save(Path(source_field.name).name, ContentFile(content), save=False)


@deconstructible
class UUIDUploadTo:
    """ImageField/FileField upload_to that stores files under <prefix>/<uuid>.<ext>."""

    def __init__(self, prefix: str):
        self.prefix = prefix.rstrip("/")

    def __call__(self, instance, filename: str) -> str:
        suffix = Path(filename).suffix.lower()
        return f"{self.prefix}/{uuid.uuid4().hex}{suffix}"

    def __eq__(self, other):
        return isinstance(other, UUIDUploadTo) and self.prefix == other.prefix
