import os
from typing import List


def parse_service_types(raw_value: str) -> List[str]:
    """Split and normalize the configured service types."""
    return [item.strip() for item in raw_value.split(",") if item.strip()]


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev_key")
    MONGO_URI = os.getenv("MONGO_URI")
    MONGO_DBNAME = os.getenv("MONGO_TARGET_DB") or os.getenv("DB_NAME") or "paris_services_gratuit"

    MAP_DEFAULT_LAT = float(os.getenv("MAP_DEFAULT_LAT", "48.8566"))
    MAP_DEFAULT_LNG = float(os.getenv("MAP_DEFAULT_LNG", "2.3522"))
    MAP_DEFAULT_ZOOM = int(os.getenv("MAP_DEFAULT_ZOOM", "12"))

    SERVICE_TYPES = parse_service_types(
        os.getenv("SERVICE_TYPES", "defibrillateurs,fontaines,toilettes,wifi")
    )
