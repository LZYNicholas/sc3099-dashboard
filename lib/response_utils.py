from typing import Any, Dict, List


def extract_items(payload: Any) -> List[Dict[str, Any]]:
    if isinstance(payload, dict):
        items = payload.get('items', [])
        return items if isinstance(items, list) else []
    if isinstance(payload, list):
        return payload
    return []


def bool_query(value: bool) -> str:
    return 'true' if value else 'false'
