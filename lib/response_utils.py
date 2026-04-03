from typing import Any, Dict, List
import requests


def extract_items(payload: Any) -> List[Dict[str, Any]]:
    if isinstance(payload, dict):
        items = payload.get('items', [])
        return items if isinstance(items, list) else []
    if isinstance(payload, list):
        return payload
    return []


def bool_query(value: bool) -> str:
    return 'true' if value else 'false'


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

        response = requests.get(url, params=page_params, headers=headers, timeout=timeout)
        if response.status_code != 200:
            break

        payload = response.json()
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
