"""
Routes Package
All API route blueprints
"""

from routes.upload import upload_bp
from routes.clean import clean_bp
from routes.download import download_bp
from routes.history import history_bp

__all__ = [
    "upload_bp",
    "clean_bp",
    "download_bp",
    "history_bp",
]