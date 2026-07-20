"""
============================================
CONFIG.PY — App Configuration
AI Data Cleaning Dashboard Backend
============================================
"""

import os
from pathlib import Path
from dotenv import load_dotenv


# ============================================
# ✅ LOAD .ENV FILE
# ============================================
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


class Config:
    """Main application config"""

    # ========================================
    # ✅ APP / FLASK SETTINGS
    # ========================================
    FLASK_APP = os.getenv("FLASK_APP", "app.py")
    FLASK_ENV = os.getenv("FLASK_ENV", "development").lower()
    DEBUG = FLASK_ENV == "development"
    TESTING = FLASK_ENV == "testing"

    SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "change-this-secret-key")

    JSON_SORT_KEYS = False
    JSONIFY_PRETTYPRINT_REGULAR = DEBUG

    # ========================================
    # ✅ PROJECT PATHS
    # ========================================
    BASE_DIR = str(BASE_DIR)
    UPLOAD_FOLDER = str(Path(BASE_DIR) / "uploads")
    CLEANED_FOLDER = str(Path(BASE_DIR) / "cleaned")
    REPORTS_FOLDER = str(Path(BASE_DIR) / "reports")

    # ========================================
    # ✅ FILE UPLOAD SETTINGS
    # ========================================
    MAX_FILE_SIZE = int(os.getenv("MAX_FILE_SIZE", 10 * 1024 * 1024))  # 10MB
    MAX_CONTENT_LENGTH = MAX_FILE_SIZE

    ALLOWED_EXTENSIONS = {"csv", "xlsx", "xls"}

    ALLOWED_MIME_TYPES = {
        "text/csv",
        "application/csv",
        "application/vnd.ms-excel",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/octet-stream",
    }

    # ========================================
    # ✅ CORS / FRONTEND ORIGINS
    # ========================================
    _raw_origins = os.getenv(
        "ALLOWED_ORIGINS",
        ",".join([
            "http://localhost:3000",
            "http://localhost:5173",
            "http://127.0.0.1:5500",
            "http://localhost:5500",
            "https://your-frontend.vercel.app",
        ])
    )

    ALLOWED_ORIGINS = [
        origin.strip()
        for origin in _raw_origins.split(",")
        if origin.strip()
    ]

    # ========================================
    # ✅ SUPABASE SETTINGS
    # ========================================
    SUPABASE_URL = os.getenv("SUPABASE_URL", "")
    SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
    SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")

    SUPABASE_UPLOAD_BUCKET = os.getenv("SUPABASE_UPLOAD_BUCKET", "uploads")
    SUPABASE_CLEANED_BUCKET = os.getenv("SUPABASE_CLEANED_BUCKET", "cleaned")
    SUPABASE_REPORT_BUCKET = os.getenv("SUPABASE_REPORT_BUCKET", "reports")

    CLEANING_JOBS_TABLE = os.getenv("CLEANING_JOBS_TABLE", "cleaning_jobs")

    # ========================================
    # ✅ CLEANING ENGINE SETTINGS
    # ========================================
    PREVIEW_ROWS = int(os.getenv("PREVIEW_ROWS", 20))
    HISTORY_PAGE_SIZE = int(os.getenv("HISTORY_PAGE_SIZE", 10))

    DEFAULT_NUMERIC_FILL = os.getenv("DEFAULT_NUMERIC_FILL", "median")
    DEFAULT_TEXT_FILL = os.getenv("DEFAULT_TEXT_FILL", "Unknown")
    DEFAULT_DATE_FORMAT = os.getenv("DEFAULT_DATE_FORMAT", "%Y-%m-%d")

    OUTLIER_METHOD = os.getenv("OUTLIER_METHOD", "iqr")
    OUTLIER_IQR_MULTIPLIER = float(os.getenv("OUTLIER_IQR_MULTIPLIER", 1.5))
    OUTLIER_ZSCORE_THRESHOLD = float(os.getenv("OUTLIER_ZSCORE_THRESHOLD", 3.0))

    AUTO_STANDARDIZE_TEXT = os.getenv("AUTO_STANDARDIZE_TEXT", "true").lower() == "true"
    AUTO_REMOVE_DUPLICATES = os.getenv("AUTO_REMOVE_DUPLICATES", "true").lower() == "true"
    AUTO_FIX_TYPES = os.getenv("AUTO_FIX_TYPES", "true").lower() == "true"
    AUTO_FILL_MISSING = os.getenv("AUTO_FILL_MISSING", "true").lower() == "true"

    # ========================================
    # ✅ JOB / STATUS SETTINGS
    # ========================================
    STATUS_PENDING = "pending"
    STATUS_UPLOADED = "uploaded"
    STATUS_PROCESSING = "processing"
    STATUS_COMPLETED = "completed"
    STATUS_FAILED = "failed"

    # ========================================
    # ✅ REPORT SETTINGS
    # ========================================
    REPORT_FILE_PREFIX = os.getenv("REPORT_FILE_PREFIX", "cleaning_report")
    CLEANED_FILE_PREFIX = os.getenv("CLEANED_FILE_PREFIX", "cleaned")
    EXPORT_JSON_INDENT = int(os.getenv("EXPORT_JSON_INDENT", 2))

    # ========================================
    # ✅ LOGGING SETTINGS
    # ========================================
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

    # ========================================
    # ✅ HELPER METHODS
    # ========================================
    @classmethod
    def is_allowed_extension(cls, filename: str) -> bool:
        """Check if file extension is allowed"""
        if not filename or "." not in filename:
            return False
        ext = filename.rsplit(".", 1)[1].lower()
        return ext in cls.ALLOWED_EXTENSIONS

    @classmethod
    def ensure_directories(cls):
        """Create required directories if they don't exist"""
        Path(cls.UPLOAD_FOLDER).mkdir(parents=True, exist_ok=True)
        Path(cls.CLEANED_FOLDER).mkdir(parents=True, exist_ok=True)
        Path(cls.REPORTS_FOLDER).mkdir(parents=True, exist_ok=True)

    @classmethod
    def validate_required_config(cls):
        """
        Validate important config values.
        Production e missing thakle error dibe.
        """
        errors = []

        if cls.FLASK_ENV == "production":
            if not cls.SUPABASE_URL:
                errors.append("SUPABASE_URL is missing")
            if not cls.SUPABASE_KEY and not cls.SUPABASE_SERVICE_ROLE_KEY:
                errors.append("SUPABASE_KEY or SUPABASE_SERVICE_ROLE_KEY is missing")
            if cls.SECRET_KEY == "change-this-secret-key":
                errors.append("FLASK_SECRET_KEY should be changed in production")

        return errors

    @classmethod
    def as_dict(cls):
        """Optional debug helper"""
        return {
            "FLASK_ENV": cls.FLASK_ENV,
            "DEBUG": cls.DEBUG,
            "UPLOAD_FOLDER": cls.UPLOAD_FOLDER,
            "CLEANED_FOLDER": cls.CLEANED_FOLDER,
            "REPORTS_FOLDER": cls.REPORTS_FOLDER,
            "MAX_FILE_SIZE": cls.MAX_FILE_SIZE,
            "ALLOWED_ORIGINS": cls.ALLOWED_ORIGINS,
            "SUPABASE_UPLOAD_BUCKET": cls.SUPABASE_UPLOAD_BUCKET,
            "SUPABASE_CLEANED_BUCKET": cls.SUPABASE_CLEANED_BUCKET,
            "SUPABASE_REPORT_BUCKET": cls.SUPABASE_REPORT_BUCKET,
            "CLEANING_JOBS_TABLE": cls.CLEANING_JOBS_TABLE,
        }


# Auto create folders on import
Config.ensure_directories()