from rest_framework.request import Request


def absolute_media_url(field_file, request: Request | None) -> str | None:
    if not field_file:
        return None
    url = field_file.url
    return request.build_absolute_uri(url) if request else url
