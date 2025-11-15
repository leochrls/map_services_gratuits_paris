from typing import Dict, Iterable, List, Optional


SERVICE_COLLECTIONS: Dict[str, str] = {
    "defibrillateurs": "defibrillateurs",
    "fontaines": "fontaines",
    "toilettes": "toilettes",
    "wifi": "wifi",
}


def normalize_service_types(configured_types: Iterable[str]) -> List[str]:
    """Keep only service types that we know how to serve."""
    valid = []
    for service in configured_types:
        if service in SERVICE_COLLECTIONS and service not in valid:
            valid.append(service)
    return valid or list(SERVICE_COLLECTIONS.keys())


def doc_to_feature(doc: Dict, service_type: str, distance_m: Optional[float] = None) -> Dict:
    """Convert a Mongo document to a GeoJSON feature."""
    geometry = doc.get("geometry")
    properties = {
        key: value
        for key, value in doc.items()
        if key not in {"_id", "geometry", "distance"}
    }
    properties["service_type"] = service_type
    if distance_m is not None:
        properties["distance_m"] = round(distance_m, 1)
    return {
        "type": "Feature",
        "geometry": geometry,
        "properties": properties,
    }


def parse_float(value: Optional[str]) -> Optional[float]:
    """Safely parse floats from query params."""
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def parse_bbox(value: Optional[str]) -> Optional[Dict[str, float]]:
    """Parse a bbox string 'south,west,north,east' into a dict."""
    if not value:
        return None
    parts = value.split(",")
    if len(parts) != 4:
        return None
    try:
        south, west, north, east = (float(part) for part in parts)
    except ValueError:
        return None
    if south >= north or west >= east:
        return None
    return {"south": south, "west": west, "north": north, "east": east}
