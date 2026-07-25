SUPPORTED_LOCALES = ("en", "uk", "fr", "es", "de")
DEFAULT_LOCALE = "en"


def resolve_locale(request) -> str:
    """Resolve the response locale from the ?lang= query param, falling back to English."""
    lang = request.query_params.get("lang", "") if request is not None else ""
    return lang if lang in SUPPORTED_LOCALES else DEFAULT_LOCALE


def localized_field(instance, base_field: str, locale: str) -> str:
    """Read `<base_field>_<locale>` off `instance`, falling back to the English variant if blank."""
    value = getattr(instance, f"{base_field}_{locale}")
    return value or getattr(instance, f"{base_field}_{DEFAULT_LOCALE}")
