from math import inf
from typing import List

from flask import Blueprint, Response, current_app, jsonify, render_template, request

from .utils import (
    SERVICE_COLLECTIONS,
    doc_to_feature,
    normalize_service_types,
    parse_bbox,
    parse_float,
)

bp = Blueprint("main", __name__)


def get_service_types() -> List[str]:
    """Return allowed service types based on configuration."""
    configured = current_app.config.get("SERVICE_TYPES", SERVICE_COLLECTIONS.keys())
    return normalize_service_types(configured)


@bp.route("/")
def map_view() -> str:
    service_types = get_service_types()
    return render_template(
        "map.html",
        service_types=service_types,
        default_center={
            "lat": current_app.config["MAP_DEFAULT_LAT"],
            "lng": current_app.config["MAP_DEFAULT_LNG"],
            "zoom": current_app.config["MAP_DEFAULT_ZOOM"],
        },
    )


@bp.route("/api/services")
def services() -> Response:
    service_type = request.args.get("type")
    limit = min(int(request.args.get("limit", "5000")), 10000)
    bbox_param = request.args.get("bbox")
    bbox = parse_bbox(bbox_param)

    # Limites officielles de Paris (fallback)
    PARIS_BBOX = {
        "min_lat": 48.8156,
        "max_lat": 48.9022,
        "min_lng": 2.2241,
        "max_lng": 2.4699,
    }

    # Vérification des types autorisés
    service_types = get_service_types()
    if service_type:
        if service_type not in service_types:
            return jsonify({"error": "Service type inconnu"}), 400
        service_types = [service_type]

    if bbox_param and bbox is None:
        return jsonify({"error": "Format bbox invalide (south,west,north,east attendu)"}), 400

    if bbox:
        min_lat = bbox["south"]
        max_lat = bbox["north"]
        min_lng = bbox["west"]
        max_lng = bbox["east"]
    else:
        min_lat = PARIS_BBOX["min_lat"]
        max_lat = PARIS_BBOX["max_lat"]
        min_lng = PARIS_BBOX["min_lng"]
        max_lng = PARIS_BBOX["max_lng"]

    polygon = {
        "type": "Polygon",
        "coordinates": [
            [
                [min_lng, min_lat],
                [max_lng, min_lat],
                [max_lng, max_lat],
                [min_lng, max_lat],
                [min_lng, min_lat],
            ]
        ],
    }
    geo_filter = {"geometry": {"$geoWithin": {"$geometry": polygon}}}

    projection = {"_id": 0}
    features = []

    # Chargement des services filtrés
    for service in service_types:
        collection = current_app.db[SERVICE_COLLECTIONS[service]]
        cursor = collection.find(geo_filter, projection).limit(limit)

        for doc in cursor:
            features.append(doc_to_feature(doc, service))

    return jsonify({"type": "FeatureCollection", "features": features})


@bp.route("/api/nearby")
def nearby() -> Response:
    lat = parse_float(request.args.get("lat"))
    lng = parse_float(request.args.get("lng"))
    limit = min(int(request.args.get("limit", "5")), 20)
    service_type = request.args.get("type")

    if lat is None or lng is None:
        return jsonify({"error": "Paramètres lat et lng requis"}), 400

    service_types = get_service_types()
    if service_type:
        if service_type not in service_types:
            return jsonify({"error": "Service type inconnu"}), 400
        service_types = [service_type]

    results = []
    for service in service_types:
        collection = current_app.db[SERVICE_COLLECTIONS[service]]
        pipeline = [
            {
                "$geoNear": {
                    "near": {"type": "Point", "coordinates": [lng, lat]},
                    "distanceField": "distance",
                    "spherical": True,
                }
            },
            {"$limit": limit},
        ]

        for doc in collection.aggregate(pipeline):
            feature = doc_to_feature(doc, service, distance_m=doc.get("distance"))
            results.append(feature)

    # keep the closest <limit> features overall
    results.sort(key=lambda feature: feature["properties"].get("distance_m", inf))
    return jsonify({"features": results[:limit]})
