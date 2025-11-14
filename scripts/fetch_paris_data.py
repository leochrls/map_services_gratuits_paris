import os
import requests 

DATASETS = {
    "fontaines": "https://opendata.paris.fr/api/explore/v2.1/catalog/datasets/fontaines-a-boire/exports/geojson?lang=fr&timezone=Europe%2FBerlin",
    "toilettes": "https://opendata.paris.fr/api/explore/v2.1/catalog/datasets/sanisettesparis/exports/geojson?lang=fr&timezone=Europe%2FBerlin",
    "wifi": "https://opendata.paris.fr/api/explore/v2.1/catalog/datasets/sites-disposant-du-service-paris-wi-fi/exports/geojson?lang=fr&timezone=Europe%2FBerlin",
    "defibrillateurs": "https://opendata.paris.fr/api/explore/v2.1/catalog/datasets/defibrillateurs/exports/geojson?lang=fr&timezone=Europe%2FBerlin",
}

OUTPUT_DIR  = os.path.join(os.path.dirname(__file__), "..", "data")
os.makedirs(OUTPUT_DIR, exist_ok=True)

def download_dataset(name: str, url: str):
    try: 
        print(f"Téléchargement de {name} ")
        response = requests.get(url)
        response.raise_for_status()

        filepath = os.path.join(OUTPUT_DIR, f"{name}.geojson")
        with open(filepath, "wb") as f:
            f.write(response.content)
        
        print(f" {name} sauvegardé dans {filepath}")
    except Exception as e:
        print(f" Erreur téléchargement {name} : {e}")

if __name__ == "__main__":
    print("=== Téléchargement des datasets Open Data Paris ===")
    for name, url in DATASETS.items():
        download_dataset(name, url)
    print("=== Terminé ===")
