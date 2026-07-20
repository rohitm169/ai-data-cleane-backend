"""
============================================
FILE_HANDLER.PY — File Management Service
Read, Save, Delete, Job Mapping
============================================
"""

import os
import json
import logging
from pathlib import Path
from typing import Optional

import pandas as pd

from config import Config

logger = logging.getLogger(__name__)


# ============================================
# ✅ JOB MAPPING FILE PATH
# Job info locally JSON e store korbo
# ============================================
MAPPING_FILE = os.path.join(Config.BASE_DIR, "job_mappings.json")


# ============================================
# ✅ FILE HANDLER CLASS
# ============================================
class FileHandler:
    """
    Static utility class for file operations.
    Read CSV/Excel, save files, manage job mappings.
    """

    # ==========================================
    # ✅ READ FILE
    # ==========================================
    @staticmethod
    def read_file(file_path: str) -> pd.DataFrame:
        """
        Read CSV or Excel file into DataFrame.

        Args:
            file_path: Full path to the file

        Returns:
            pandas DataFrame

        Raises:
            ValueError: If file format not supported
            Exception:  If file cannot be read
        """
        try:
            if not os.path.exists(file_path):
                raise FileNotFoundError(
                    f"File not found: {file_path}"
                )

            ext = Path(file_path).suffix.lower()

            logger.info(f"📖 Reading file: {file_path} ({ext})")

            # ── CSV ──
            if ext == '.csv':
                df = FileHandler._read_csv(file_path)

            # ── Excel ──
            elif ext in ('.xlsx', '.xls'):
                df = FileHandler._read_excel(file_path)

            else:
                raise ValueError(
                    f"Unsupported file format: {ext}. "
                    f"Use CSV, XLSX or XLS."
                )

            # Basic validation
            if df.empty:
                raise ValueError("File is empty or has no data.")

            if len(df.columns) == 0:
                raise ValueError("File has no columns.")

            # Clean column names
            df = FileHandler._clean_column_names(df)

            logger.info(
                f"✅ File read: {df.shape[0]} rows × "
                f"{df.shape[1]} cols"
            )

            return df

        except FileNotFoundError as e:
            logger.error(f"❌ File not found: {e}")
            raise

        except ValueError as e:
            logger.error(f"❌ File read ValueError: {e}")
            raise

        except Exception as e:
            logger.error(f"❌ File read error: {e}")
            raise Exception(f"Could not read file: {str(e)}")


    # ==========================================
    # ✅ READ CSV (with encoding detection)
    # ==========================================
    @staticmethod
    def _read_csv(file_path: str) -> pd.DataFrame:
        """
        Read CSV with multiple encoding attempts.
        Tries utf-8, latin-1, cp1252 in order.
        """
        encodings = ['utf-8', 'latin-1', 'cp1252', 'iso-8859-1']
        separators = [',', ';', '\t', '|']

        last_error = None

        for encoding in encodings:
            for sep in separators:
                try:
                    df = pd.read_csv(
                        file_path,
                        encoding=encoding,
                        sep=sep,
                        on_bad_lines='skip',
                        low_memory=False,
                    )

                    # Valid if has more than 1 column or sep was comma
                    if len(df.columns) >= 1 and len(df) > 0:
                        logger.info(
                            f"✅ CSV read: encoding={encoding}, "
                            f"sep='{sep}'"
                        )
                        return df

                except Exception as e:
                    last_error = e
                    continue

        raise Exception(
            f"Could not read CSV file. "
            f"Last error: {last_error}"
        )


    # ==========================================
    # ✅ READ EXCEL
    # ==========================================
    @staticmethod
    def _read_excel(file_path: str) -> pd.DataFrame:
        """
        Read Excel file.
        Tries first sheet by default.
        """
        try:
            # Try reading first sheet
            df = pd.read_excel(
                file_path,
                sheet_name=0,
                engine='openpyxl',
            )

            if df.empty:
                # Try all sheets and use first non-empty
                xl = pd.ExcelFile(file_path, engine='openpyxl')
                for sheet in xl.sheet_names:
                    df = pd.read_excel(
                        file_path,
                        sheet_name=sheet,
                        engine='openpyxl',
                    )
                    if not df.empty:
                        logger.info(f"✅ Excel sheet used: '{sheet}'")
                        return df

            return df

        except Exception as e:
            # Try xlrd for older .xls
            try:
                df = pd.read_excel(
                    file_path,
                    sheet_name=0,
                    engine='xlrd',
                )
                return df
            except Exception:
                raise Exception(
                    f"Could not read Excel file: {str(e)}"
                )


    # ==========================================
    # ✅ CLEAN COLUMN NAMES
    # ==========================================
    @staticmethod
    def _clean_column_names(df: pd.DataFrame) -> pd.DataFrame:
        """
        Clean DataFrame column names.
        - Strip whitespace
        - Replace spaces with underscore
        - Remove special characters
        - Handle duplicate column names
        """
        try:
            new_cols = []
            seen = {}

            for col in df.columns:
                # Convert to string
                clean = str(col).strip()

                # Replace spaces and special chars
                clean = clean.replace(' ', '_')
                clean = ''.join(
                    c for c in clean
                    if c.isalnum() or c in ('_', '-', '.')
                )

                # Remove leading numbers
                if clean and clean[0].isdigit():
                    clean = f"col_{clean}"

                # Handle empty column names
                if not clean:
                    clean = f"column_{len(new_cols)}"

                # Handle duplicates
                if clean in seen:
                    seen[clean] += 1
                    clean = f"{clean}_{seen[clean]}"
                else:
                    seen[clean] = 0

                new_cols.append(clean)

            df.columns = new_cols
            return df

        except Exception as e:
            logger.warning(f"⚠️ Column name cleaning failed: {e}")
            return df


    # ==========================================
    # ✅ SAVE DATAFRAME TO CSV
    # ==========================================
    @staticmethod
    def save_as_csv(
        df: pd.DataFrame,
        file_path: str,
        index: bool = False,
    ) -> str:
        """
        Save DataFrame as CSV file.

        Args:
            df        : DataFrame to save
            file_path : Output file path
            index     : Include index (default False)

        Returns:
            Saved file path
        """
        try:
            # Ensure directory exists
            os.makedirs(
                os.path.dirname(file_path),
                exist_ok=True
            )

            df.to_csv(file_path, index=index, encoding='utf-8')

            file_size = os.path.getsize(file_path)
            logger.info(
                f"💾 Saved CSV: {file_path} "
                f"({FileHandler.format_file_size(file_size)})"
            )

            return file_path

        except Exception as e:
            logger.error(f"❌ save_as_csv error: {e}")
            raise


    # ==========================================
    # ✅ DELETE LOCAL FILE
    # ==========================================
    @staticmethod
    def delete_local_file(file_path: str) -> bool:
        """
        Delete a local file.

        Args:
            file_path: Path to file to delete

        Returns:
            True if deleted, False if not found
        """
        try:
            if not file_path:
                return False

            if os.path.exists(file_path):
                os.remove(file_path)
                logger.info(f"🗑️ File deleted: {file_path}")
                return True

            return False

        except Exception as e:
            logger.error(f"❌ delete_local_file error: {e}")
            return False


    # ==========================================
    # ✅ FORMAT FILE SIZE
    # ==========================================
    @staticmethod
    def format_file_size(size_bytes: int) -> str:
        """
        Convert bytes to human readable string.

        Args:
            size_bytes: File size in bytes

        Returns:
            Formatted string like '2.4 MB'
        """
        if size_bytes == 0:
            return "0 B"

        units = ["B", "KB", "MB", "GB"]
        index = 0

        size = float(size_bytes)

        while size >= 1024 and index < len(units) - 1:
            size /= 1024
            index += 1

        return f"{size:.1f} {units[index]}"


    # ==========================================
    # ✅ LOAD JOB MAPPINGS FILE
    # ==========================================
    @staticmethod
    def _load_mappings() -> dict:
        """
        Load all job mappings from JSON file.
        Returns empty dict if file not found.
        """
        try:
            if not os.path.exists(MAPPING_FILE):
                return {}

            with open(MAPPING_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)

        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"⚠️ Could not load mappings: {e}")
            return {}


    # ==========================================
    # ✅ SAVE JOB MAPPINGS FILE
    # ==========================================
    @staticmethod
    def _save_mappings(mappings: dict):
        """
        Save all job mappings to JSON file.
        """
        try:
            os.makedirs(
                os.path.dirname(MAPPING_FILE)
                if os.path.dirname(MAPPING_FILE)
                else Config.BASE_DIR,
                exist_ok=True
            )

            with open(MAPPING_FILE, 'w', encoding='utf-8') as f:
                json.dump(mappings, f, indent=2, default=str)

        except Exception as e:
            logger.error(f"❌ _save_mappings error: {e}")


    # ==========================================
    # ✅ SAVE JOB MAPPING
    # ==========================================
    @staticmethod
    def save_job_mapping(job_id: str, data: dict):
        """
        Save job info to local JSON mapping.

        Args:
            job_id: Unique job identifier
            data  : Job data dict to save
        """
        try:
            mappings = FileHandler._load_mappings()

            # Merge with existing if present
            existing = mappings.get(job_id, {})
            existing.update(data)

            # Add timestamps
            if 'created_at' not in existing:
                from datetime import datetime
                existing['created_at'] = (
                    datetime.utcnow().isoformat()
                )

            mappings[job_id] = existing

            FileHandler._save_mappings(mappings)

            logger.info(f"💾 Job mapping saved: {job_id}")

        except Exception as e:
            logger.error(f"❌ save_job_mapping error: {e}")


    # ==========================================
    # ✅ GET JOB MAPPING
    # ==========================================
    @staticmethod
    def get_job_mapping(job_id: str) -> Optional[dict]:
        """
        Get job info from local JSON mapping.

        Args:
            job_id: Unique job identifier

        Returns:
            Job data dict or None if not found
        """
        try:
            mappings = FileHandler._load_mappings()
            mapping = mappings.get(job_id)

            if mapping:
                logger.debug(f"📋 Job mapping found: {job_id}")
            else:
                logger.debug(f"📋 Job mapping not found: {job_id}")

            return mapping

        except Exception as e:
            logger.error(f"❌ get_job_mapping error: {e}")
            return None


    # ==========================================
    # ✅ GET ALL JOB MAPPINGS
    # ==========================================
    @staticmethod
    def get_all_job_mappings() -> dict:
        """
        Get all job mappings.

        Returns:
            Dict of all job mappings { job_id: data }
        """
        try:
            return FileHandler._load_mappings()
        except Exception as e:
            logger.error(f"❌ get_all_job_mappings error: {e}")
            return {}


    # ==========================================
    # ✅ DELETE JOB MAPPING
    # ==========================================
    @staticmethod
    def delete_job_mapping(job_id: str) -> bool:
        """
        Remove job from local JSON mapping.

        Args:
            job_id: Unique job identifier

        Returns:
            True if deleted, False if not found
        """
        try:
            mappings = FileHandler._load_mappings()

            if job_id in mappings:
                del mappings[job_id]
                FileHandler._save_mappings(mappings)
                logger.info(f"🗑️ Job mapping deleted: {job_id}")
                return True

            return False

        except Exception as e:
            logger.error(f"❌ delete_job_mapping error: {e}")
            return False


    # ==========================================
    # ✅ CLEANUP OLD FILES
    # ==========================================
    @staticmethod
    def cleanup_old_files(max_age_hours: int = 24):
        """
        Delete local files older than max_age_hours.
        Runs on upload folder and cleaned folder.

        Args:
            max_age_hours: Files older than this will be deleted
        """
        import time

        try:
            now = time.time()
            max_age_seconds = max_age_hours * 3600
            deleted_count = 0

            folders = [
                Config.UPLOAD_FOLDER,
                Config.CLEANED_FOLDER,
                Config.REPORTS_FOLDER,
            ]

            for folder in folders:
                if not os.path.exists(folder):
                    continue

                for filename in os.listdir(folder):
                    file_path = os.path.join(folder, filename)

                    if not os.path.isfile(file_path):
                        continue

                    file_age = now - os.path.getmtime(file_path)

                    if file_age > max_age_seconds:
                        try:
                            os.remove(file_path)
                            deleted_count += 1
                            logger.info(
                                f"🧹 Old file deleted: {file_path}"
                            )
                        except Exception as e:
                            logger.warning(
                                f"⚠️ Could not delete {file_path}: {e}"
                            )

            logger.info(
                f"🧹 Cleanup complete: {deleted_count} files deleted"
            )
            return deleted_count

        except Exception as e:
            logger.error(f"❌ cleanup_old_files error: {e}")
            return 0


    # ==========================================
    # ✅ GET FILE INFO
    # ==========================================
    @staticmethod
    def get_file_info(file_path: str) -> dict:
        """
        Get file metadata.

        Args:
            file_path: Path to file

        Returns:
            Dict with name, size, extension, exists
        """
        try:
            path = Path(file_path)

            if not path.exists():
                return {
                    'exists': False,
                    'name': path.name,
                    'size': 0,
                    'size_str': '0 B',
                    'extension': path.suffix.lower(),
                }

            size = path.stat().st_size

            return {
                'exists': True,
                'name': path.name,
                'size': size,
                'size_str': FileHandler.format_file_size(size),
                'extension': path.suffix.lower(),
                'modified_at': path.stat().st_mtime,
            }

        except Exception as e:
            logger.error(f"❌ get_file_info error: {e}")
            return {
                'exists': False,
                'name': '',
                'size': 0,
                'size_str': '0 B',
                'extension': '',
            }


    # ==========================================
    # ✅ CHECK FILE EXISTS
    # ==========================================
    @staticmethod
    def file_exists(file_path: str) -> bool:
        """Check if a file exists at given path"""
        return bool(file_path) and os.path.exists(file_path)


    # ==========================================
    # ✅ ENSURE DIRECTORIES EXIST
    # ==========================================
    @staticmethod
    def ensure_directories():
        """Create required directories if missing"""
        dirs = [
            Config.UPLOAD_FOLDER,
            Config.CLEANED_FOLDER,
            Config.REPORTS_FOLDER,
        ]
        for d in dirs:
            os.makedirs(d, exist_ok=True)
            logger.debug(f"📁 Directory ready: {d}")