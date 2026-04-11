from typing import Any, Dict, List, Optional, Tuple
import requests
import time

def extract_items(payload: Any) -> List[Dict[str, Any]]:
    if isinstance(payload, dict):
        items = payload.get('items', [])
        return items if isinstance(items, list) else []
    if isinstance(payload, list):
        return payload
    return []


def bool_query(value: bool) -> str:
    return 'true' if value else 'false'


def parse_json(response: requests.Response | None) -> Any:
    if response is None:
        return None
    try:
        return response.json()
    except Exception:
        return None


def friendly_error(error: Any, fallback: str = "Something went wrong. Please try again.") -> str:
    """Convert technical errors into clear, user-facing messages."""
    raw = str(error or "").strip()
    if not raw:
        return fallback

    text = raw.lower()

    if any(token in text for token in ("timed out", "timeout", "connection error", "connection refused", "failed to connect", "max retries exceeded", "name or service not known")):
        return "We couldn't reach the service. Please try again in a moment."

    if any(token in text for token in ("database operation failed", "database", "prisma", "sql", "foreign key")):
        return "We couldn't save your request right now. Please try again."

    if any(token in text for token in ("duplicate", "already exists", "unique constraint", "unique failed")):
        return "This record already exists. Try a different name or value."

    if any(token in text for token in ("unauthorized", "forbidden", "invalid token", "token expired", "access denied")):
        return "Your session has expired or you do not have permission for this action."

    if any(token in text for token in ("bad request", "validation", "unprocessable", "invalid input", "invalid payload")):
        return "Some fields look invalid. Please review and try again."

    if any(token in text for token in ("not found", "does not exist")):
        return "We couldn't find the requested record. Please refresh and try again."

    if any(token in text for token in ("internal server error", "error 500")):
        return "The server ran into an issue. Please try again shortly."

    # Preserve short, already-human messages.
    if len(raw) <= 90 and "error" not in text:
        return raw

    return fallback


def response_error(response: requests.Response | None, fallback: str = "Unknown error") -> str:
    if response is None:
        return friendly_error("connection error", fallback=fallback)

    payload = parse_json(response)
    if isinstance(payload, dict):
        detail = payload.get("detail") or payload.get("message") or payload.get("error")
        if detail:
            return friendly_error(detail, fallback=fallback)

    text = (response.text or "").strip()
    if text:
        return friendly_error(text[:250], fallback=fallback)
    return friendly_error(fallback, fallback=fallback)


def request_with_retry(
    method: str,
    url: str,
    *,
    headers: Dict[str, str] | None = None,
    params: Dict[str, Any] | None = None,
    json: Dict[str, Any] | List[Any] | None = None,
    data: Any = None,
    timeout: int = 10,
    retries: int = 2,
    backoff_base: float = 0.35,
    retry_for: tuple[int, ...] = (408, 425, 429, 500, 502, 503, 504),
) -> Tuple[requests.Response | None, Optional[str]]:
    """Send an HTTP request with bounded retries for transient failures."""
    last_error: Optional[str] = None

    for attempt in range(retries + 1):
        try:
            response = requests.request(
                method=method,
                url=url,
                headers=headers,
                params=params,
                json=json,
                data=data,
                timeout=timeout,
            )
            if response.status_code in retry_for and attempt < retries:
                time.sleep(backoff_base * (2 ** attempt))
                continue
            return response, None
        except requests.RequestException as error:
            last_error = str(error)
            if attempt < retries:
                time.sleep(backoff_base * (2 ** attempt))
                continue
            return None, last_error

    return None, last_error or "Request failed"


def fetch_all_items(
    url: str,
    headers: Dict[str, str],
    params: Dict[str, Any] | None = None,
    *,
    timeout: int = 10,
    page_size: int = 200,
    max_pages: int = 100,
) -> List[Dict[str, Any]]:
    """Fetch all paginated records from an endpoint supporting limit/offset.

    Safely falls back to first page only if endpoint does not expose pagination fields.
    """
    base_params = dict(params or {})
    items: List[Dict[str, Any]] = []
    offset = int(base_params.pop('offset', 0) or 0)

    for _ in range(max_pages):
        page_params = dict(base_params)
        page_params['limit'] = page_size
        page_params['offset'] = offset

        response, error = request_with_retry(
            "GET",
            url,
            params=page_params,
            headers=headers,
            timeout=timeout,
        )
        if response is None or error is not None or response.status_code != 200:
            break

        payload = parse_json(response)
        page_items = extract_items(payload)
        if not page_items:
            break

        items.extend(page_items)

        if isinstance(payload, dict):
            total = payload.get('total')
            if isinstance(total, int) and len(items) >= total:
                break

        if len(page_items) < page_size:
            break

        offset += page_size

    return items
