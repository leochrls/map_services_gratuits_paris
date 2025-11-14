import json
import os
from pathlib import Path
from typing import Dict, Iterable

from dotenv import load_dotenv
from pymongo import GEOSPHERE, MongoClient


load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
TARGET_DB_NAME = os.getenv("MONGO_TARGET_DB", "paris_services_gratuit")

if not MONGO_URI:
    raise ValueError("MONGO_URI est manquant. Verifie ton fichier .env.")

client = MongoClient(MONGO_URI)
db = client[TARGET_DB_NAME]

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


CLEANING_RULES: Dict[str, Dict[str, Iterable[str]]] = {
    "fontaines": {
        "keep": [
            "voie",
            "commune",
            "modele",
            "dispo",
        ],
        "rename": {
            "voie": "adresse",
            "dispo": "disponible",
        },
        "drop": [
            "gid",
            "debut ind",
            "debut_ind",
            "fin ind",
            "fin_ind",
            "motif ind",
            "motif_ind",
            "no voirie pair",
            "no_voirie_pair",
            "no voirie impair",
            "no_voirie_impair",
            "geo point 2d",
        ],
    },
    "defibrillateurs": {
        "keep": [
            "adr post",
            "adr_post",
            "code post",
            "code_post",
            "commune",
            "etat inst",
            "etat_inst",
            "nom etabl",
            "nom_etabl",
            "type etabl",
            "type_etabl",
            "cplmt info",
            "cplmt_info",
        ],
        "rename": {
            "adr post": "adresse",
            "adr_post": "adresse",
            "code post": "code_postal",
            "code_post": "code_postal",
            "etat inst": "etat",
            "etat_inst": "etat",
            "nom etabl": "nom",
            "nom_etabl": "nom",
            "type etabl": "type_etablissement",
            "type_etabl": "type_etablissement",
            "cplmt info": "complement",
            "cplmt_info": "complement",
        },
        "drop": [
            "objectid",
            "geo point 2d",
            "geo_point_2d",
        ],
    },
    "wifi": {
        "keep": [
            "nom site",
            "nom_site",
            "arc adresse",
            "arc_adresse",
            "cp",
            "nombre de borne wifi",
            "nombre_de_borne_wifi",
            "etat2",
        ],
        "rename": {
            "nom site": "nom",
            "nom_site": "nom",
            "arc adresse": "adresse",
            "arc_adresse": "adresse",
            "cp": "code_postal",
            "nombre de borne wifi": "bornes",
            "nombre_de_borne_wifi": "bornes",
            "etat2": "etat",
        },
        "drop": [
            "idpw",
            "geo point 2d",
        ],
    },
    "toilettes": {
        "keep": [
            "adresse",
            "arrondissement",
            "acces pmr",
            "acces_pmr",
            "horaire",
            "horaires",
            "relais bebe",
            "relais_bebe",
            "type",
        ],
        "rename": {
            "acces pmr": "pmr",
            "acces_pmr": "pmr",
            "horaire": "horaires",
            "relais bebe": "relais_bebe",
            "relais_bebe": "relais_bebe",
        },
        "drop": [
            "statut",
            "url fiche equipement",
            "url_fiche_equipement",
            "geo point 2d",
        ],
    },
}

DEFAULT_DROP_FIELDS = {"geo_point_2d", "geo_point_2d_2", "geo point 2d"}


def clean_properties(collection_name: str, properties: Dict) -> Dict:
    """Apply per-collection cleaning/renaming rules."""
    rules = CLEANING_RULES.get(collection_name, {})
    keep = set(rules.get("keep", []))
    rename = rules.get("rename", {})
    drops = set(rules.get("drop", []))

    cleaned = {}
    for key, value in properties.items():
        if key in drops or key in DEFAULT_DROP_FIELDS:
            continue
        if keep and key not in keep:
            continue
        final_key = rename.get(key, key)
        cleaned[final_key] = value
    return cleaned


def extract_lat_lon(geometry: Dict) -> Dict:
    """Extract longitude/latitude from GeoJSON geometry."""
    if not geometry:
        return {}
    coordinates = geometry.get("coordinates")
    if (
        isinstance(coordinates, (list, tuple))
        and len(coordinates) >= 2
        and isinstance(coordinates[0], (int, float))
    ):
        lon, lat = coordinates[0], coordinates[1]
        return {"longitude": lon, "latitude": lat}
    return {}


def load_geojson_to_mongo(file_path: Path) -> None:
    """Charge un GeoJSON dans la collection Mongo correspondante."""
    collection_name = file_path.stem
    print(f" Import de '{collection_name}' ...")

    with file_path.open("r", encoding="utf-8") as source:
        data = json.load(source)

    features = data.get("features", [])
    if not features:
        print(f" Aucun feature trouve dans {file_path.name}")
        return

    docs = []
    for feature in features:
        geometry = feature.get("geometry")
        properties = feature.get("properties", {})
        cleaned = clean_properties(collection_name, properties)
        cleaned.update(extract_lat_lon(geometry))
        cleaned["geometry"] = geometry
        docs.append(cleaned)

    collection = db[collection_name]
    collection.delete_many({})  # reset collection before loading
    if docs:
        collection.insert_many(docs)
        collection.create_index([("geometry", GEOSPHERE)])
    print(f" {len(docs)} documents inseres dans '{collection_name}'")


if __name__ == "__main__":
    print("=== Chargement des fichiers GeoJSON vers MongoDB Atlas ===")

    geojson_files = sorted(DATA_DIR.glob("*.geojson"))
    if not geojson_files:
        raise FileNotFoundError(f"Aucun fichier *.geojson trouve dans {DATA_DIR}")

    for file_path in geojson_files:
        load_geojson_to_mongo(file_path)

    print(f"=== Termine. Base utilisee : '{TARGET_DB_NAME}' ===")
