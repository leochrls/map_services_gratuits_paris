from dotenv import load_dotenv
load_dotenv()

from flask import Flask
from pymongo import MongoClient

from .config import Config


def create_app() -> Flask:
    """Application factory."""
    app = Flask(__name__)
    app.config.from_object(Config)

    mongo_uri = app.config.get("MONGO_URI")
    if not mongo_uri:
        raise RuntimeError("MONGO_URI n'est pas défini. Configure-le dans ton environnement.")

    mongo_client = MongoClient(mongo_uri)
    app.mongo_client = mongo_client
    app.db = mongo_client[app.config["MONGO_DBNAME"]]

    from .routes import bp as routes_bp

    app.register_blueprint(routes_bp)
    return app


app = create_app()
