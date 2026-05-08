from rest_framework.request import Request

from apps.common.constants import MAX_TOP_N_LIMIT
from apps.common.exceptions import InvalidLimitError


def parse_limit(request: Request, default: int) -> int:
    raw = request.query_params.get("limit")
    if raw is None:
        return default
    try:
        value = int(raw)
    except (TypeError, ValueError):
        raise InvalidLimitError("limit must be a positive integer")
    if value <= 0:
        raise InvalidLimitError("limit must be a positive integer")
    return min(value, MAX_TOP_N_LIMIT)
