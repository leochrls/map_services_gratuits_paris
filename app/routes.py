from math import inf
from typing import List

from flask import Blueprint, Response, current_app, jsonify, render_template, request

from .utils import SERVICE_COLLECTIONS, doc_to_feature, normalize_service_types, parse_float

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

    service_types = get_service_types()
    if service_type:
        if service_type not in service_types:
            return jsonify({"error": "Service type inconnu"}), 400
        service_types = [service_type]

    features = []
    projection = {"_id": 0}
    for service in service_types:
        collection = current_app.db[SERVICE_COLLECTIONS[service]]
        cursor = collection.find({}, projection).limit(limit)
        for doc in cursor:
            features.append(doc_to_feature(doc, service))
    return jsonify({"features": features})


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
