"""
============================================
DATABASE.PY — Supabase Connection & Queries
AI Data Cleaning Dashboard Backend
============================================
"""

import logging
from datetime import datetime
from typing import Optional

from supabase import create_client, Client
from config import Config

logger = logging.getLogger(__name__)


# ============================================
# ✅ DATABASE CLASS
# ============================================
class Database:
    """
    Supabase database connection
    and all CRUD operations
    """

    def __init__(self):
        """Initialize Supabase client"""
        self.client: Optional[Client] = None
        self.table = Config.CLEANING_JOBS_TABLE
        self._connect()


    # ==========================================
    # ✅ CONNECTION
    # ==========================================
    def _connect(self):
        """Connect to Supabase"""
        try:
            if not Config.SUPABASE_URL or not Config.SUPABASE_KEY:
                raise ValueError(
                    "SUPABASE_URL or SUPABASE_KEY is missing in .env"
                )

            self.client = create_client(
                Config.SUPABASE_URL,
                Config.SUPABASE_SERVICE_ROLE_KEY or Config.SUPABASE_KEY
            )

            logger.info("✅ Supabase client initialized")

        except Exception as e:
            logger.error(f"❌ Supabase connection error: {e}")
            raise


    # ==========================================
    # ✅ HEALTH CHECK
    # ==========================================
    def health_check(self) -> bool:
        """Check if Supabase is reachable"""
        try:
            self.client.table(self.table).select("id").limit(1).execute()
            return True
        except Exception as e:
            logger.error(f"❌ Health check failed: {e}")
            return False


    # ==========================================
    # ✅ CREATE JOB
    # ==========================================
    def create_job(self, job_data: dict) -> dict:
        """
        Create a new cleaning job record
        Returns created job dict
        """
        try:
            payload = {
                "original_name":     job_data.get("original_name", ""),
                "original_rows":     job_data.get("original_rows", 0),
                "original_cols":     job_data.get("original_cols", 0),
                "cleaned_rows":      0,
                "duplicates_removed":0,
                "missing_filled":    0,
                "types_fixed":       0,
                "text_standardized": 0,
                "outliers_found":    0,
                "quality_score":     0.0,
                "cleaning_options":  job_data.get("cleaning_options", {}),
                "report_data":       {},
                "original_file_url": job_data.get("original_file_url", ""),
                "cleaned_file_url":  "",
                "file_size":         job_data.get("file_size", ""),
                "file_type":         job_data.get("file_type", ""),
                "status":            Config.STATUS_UPLOADED,
                "error_message":     "",
                "created_at":        datetime.utcnow().isoformat(),
                "updated_at":        datetime.utcnow().isoformat(),
            }

            response = (
                self.client
                .table(self.table)
                .insert(payload)
                .execute()
            )

            if response.data:
                logger.info(f"✅ Job created: {response.data[0]['id']}")
                return response.data[0]

            raise Exception("No data returned from insert")

        except Exception as e:
            logger.error(f"❌ create_job error: {e}")
            raise


    # ==========================================
    # ✅ GET JOB BY ID
    # ==========================================
    def get_job(self, job_id: str) -> Optional[dict]:
        """
        Get single job by ID
        Returns job dict or None
        """
        try:
            response = (
                self.client
                .table(self.table)
                .select("*")
                .eq("id", job_id)
                .single()
                .execute()
            )

            if response.data:
                return response.data

            return None

        except Exception as e:
            logger.error(f"❌ get_job error: {e}")
            return None


    # ==========================================
    # ✅ UPDATE JOB
    # ==========================================
    def update_job(self, job_id: str, update_data: dict) -> Optional[dict]:
        """
        Update job record by ID
        Returns updated job dict or None
        """
        try:
            # Always update updated_at
            update_data["updated_at"] = datetime.utcnow().isoformat()

            response = (
                self.client
                .table(self.table)
                .update(update_data)
                .eq("id", job_id)
                .execute()
            )

            if response.data:
                logger.info(f"✅ Job updated: {job_id}")
                return response.data[0]

            return None

        except Exception as e:
            logger.error(f"❌ update_job error: {e}")
            raise


    # ==========================================
    # ✅ UPDATE JOB STATUS
    # ==========================================
    def update_status(
        self,
        job_id: str,
        status: str,
        message: str = ""
    ) -> Optional[dict]:
        """
        Update only the status of a job
        """
        try:
            payload = {
                "status": status,
                "updated_at": datetime.utcnow().isoformat(),
            }

            if message:
                payload["error_message"] = message

            response = (
                self.client
                .table(self.table)
                .update(payload)
                .eq("id", job_id)
                .execute()
            )

            logger.info(f"🔄 Job {job_id} status → {status}")

            if response.data:
                return response.data[0]
            return None

        except Exception as e:
            logger.error(f"❌ update_status error: {e}")
            raise


    # ==========================================
    # ✅ SAVE CLEANING RESULTS
    # ==========================================
    def save_results(self, job_id: str, results: dict) -> Optional[dict]:
        """
        Save full cleaning results to database
        Called after cleaning is complete
        """
        try:
            payload = {
                "status":             Config.STATUS_COMPLETED,
                "cleaned_rows":       results.get("cleaned_rows", 0),
                "duplicates_removed": results.get("duplicates_removed", 0),
                "missing_filled":     results.get("missing_filled", 0),
                "types_fixed":        results.get("types_fixed", 0),
                "text_standardized":  results.get("text_standardized", 0),
                "outliers_found":     results.get("outliers_found", 0),
                "quality_score":      results.get("quality_score", 0.0),
                "cleaned_file_url":   results.get("cleaned_file_url", ""),
                "report_data":        results.get("report_data", {}),
                "updated_at":         datetime.utcnow().isoformat(),
            }

            response = (
                self.client
                .table(self.table)
                .update(payload)
                .eq("id", job_id)
                .execute()
            )

            logger.info(f"✅ Results saved for job: {job_id}")

            if response.data:
                return response.data[0]
            return None

        except Exception as e:
            logger.error(f"❌ save_results error: {e}")
            raise


    # ==========================================
    # ✅ GET ALL JOBS (History)
    # ==========================================
    def get_all_jobs(
        self,
        page: int = 1,
        limit: int = 10,
        search: str = "",
        date_filter: str = "all",
        score_filter: str = "all",
        sort: str = "newest",
    ) -> dict:
        """
        Get paginated list of cleaning jobs
        Returns { jobs, total, page, limit }
        """
        try:
            query = (
                self.client
                .table(self.table)
                .select("*", count="exact")
            )

            # ── Search Filter ──
            if search:
                query = query.ilike("original_name", f"%{search}%")

            # ── Date Filter ──
            if date_filter == "today":
                today = datetime.utcnow().strftime("%Y-%m-%d")
                query = query.gte("created_at", f"{today}T00:00:00")

            elif date_filter == "week":
                from datetime import timedelta
                week_ago = (
                    datetime.utcnow() - timedelta(days=7)
                ).strftime("%Y-%m-%d")
                query = query.gte("created_at", f"{week_ago}T00:00:00")

            elif date_filter == "month":
                from datetime import timedelta
                month_ago = (
                    datetime.utcnow() - timedelta(days=30)
                ).strftime("%Y-%m-%d")
                query = query.gte("created_at", f"{month_ago}T00:00:00")

            # ── Score Filter ──
            if score_filter == "excellent":
                query = query.gte("quality_score", 90)

            elif score_filter == "good":
                query = query.gte("quality_score", 70).lt("quality_score", 90)

            elif score_filter == "fair":
                query = query.gte("quality_score", 50).lt("quality_score", 70)

            elif score_filter == "poor":
                query = query.lt("quality_score", 50)

            # ── Sort ──
            if sort == "newest":
                query = query.order("created_at", desc=True)

            elif sort == "oldest":
                query = query.order("created_at", desc=False)

            elif sort == "score-high":
                query = query.order("quality_score", desc=True)

            elif sort == "score-low":
                query = query.order("quality_score", desc=False)

            elif sort == "rows-high":
                query = query.order("original_rows", desc=True)

            else:
                query = query.order("created_at", desc=True)

            # ── Pagination ──
            offset = (page - 1) * limit
            query = query.range(offset, offset + limit - 1)

            response = query.execute()

            return {
                "jobs":  response.data or [],
                "total": response.count or 0,
                "page":  page,
                "limit": limit,
                "pages": (
                    (response.count + limit - 1) // limit
                    if response.count else 0
                ),
            }

        except Exception as e:
            logger.error(f"❌ get_all_jobs error: {e}")
            raise


    # ==========================================
    # ✅ GET HISTORY STATS
    # ==========================================
    def get_stats(self) -> dict:
        """
        Get overview stats for history page
        Returns { total_jobs, total_rows, total_issues, avg_score }
        """
        try:
            response = (
                self.client
                .table(self.table)
                .select(
                    "id, original_rows, duplicates_removed, "
                    "missing_filled, types_fixed, text_standardized, "
                    "outliers_found, quality_score, status"
                )
                .eq("status", Config.STATUS_COMPLETED)
                .execute()
            )

            jobs = response.data or []

            if not jobs:
                return {
                    "total_jobs": 0,
                    "total_rows": 0,
                    "total_issues": 0,
                    "avg_score": 0,
                }

            total_rows = sum(j.get("original_rows", 0) for j in jobs)
            total_issues = sum(
                j.get("duplicates_removed", 0) +
                j.get("missing_filled", 0) +
                j.get("types_fixed", 0) +
                j.get("text_standardized", 0) +
                j.get("outliers_found", 0)
                for j in jobs
            )
            avg_score = round(
                sum(j.get("quality_score", 0) for j in jobs) / len(jobs), 1
            )

            # All jobs count (including failed, processing)
            all_jobs_response = (
                self.client
                .table(self.table)
                .select("id", count="exact")
                .execute()
            )

            return {
                "total_jobs":   all_jobs_response.count or len(jobs),
                "total_rows":   total_rows,
                "total_issues": total_issues,
                "avg_score":    avg_score,
            }

        except Exception as e:
            logger.error(f"❌ get_stats error: {e}")
            raise


    # ==========================================
    # ✅ DELETE JOB
    # ==========================================
    def delete_job(self, job_id: str) -> bool:
        """
        Delete a single job by ID
        Returns True if successful
        """
        try:
            self.client \
                .table(self.table) \
                .delete() \
                .eq("id", job_id) \
                .execute()

            logger.info(f"🗑️ Job deleted: {job_id}")
            return True

        except Exception as e:
            logger.error(f"❌ delete_job error: {e}")
            raise


    # ==========================================
    # ✅ BULK DELETE JOBS
    # ==========================================
    def delete_multiple_jobs(self, job_ids: list) -> int:
        """
        Delete multiple jobs by ID list
        Returns count of deleted jobs
        """
        try:
            if not job_ids:
                return 0

            self.client \
                .table(self.table) \
                .delete() \
                .in_("id", job_ids) \
                .execute()

            logger.info(f"🗑️ Bulk deleted {len(job_ids)} jobs")
            return len(job_ids)

        except Exception as e:
            logger.error(f"❌ delete_multiple_jobs error: {e}")
            raise


    # ==========================================
    # ✅ UPLOAD FILE TO SUPABASE STORAGE
    # ==========================================
    def upload_file_to_storage(
        self,
        bucket: str,
        file_path: str,
        file_data: bytes,
        content_type: str = "text/csv"
    ) -> str:
        """
        Upload file bytes to Supabase Storage
        Returns public URL of uploaded file
        """
        try:
            self.client.storage \
                .from_(bucket) \
                .upload(
                    path=file_path,
                    file=file_data,
                    file_options={"content-type": content_type}
                )

            # Get public URL
            url_response = self.client.storage \
                .from_(bucket) \
                .get_public_url(file_path)

            logger.info(f"☁️ File uploaded to storage: {bucket}/{file_path}")
            return url_response

        except Exception as e:
            logger.error(f"❌ upload_file_to_storage error: {e}")
            raise


    # ==========================================
    # ✅ DELETE FILE FROM SUPABASE STORAGE
    # ==========================================
    def delete_file_from_storage(
        self,
        bucket: str,
        file_path: str
    ) -> bool:
        """
        Delete a file from Supabase Storage
        Returns True if successful
        """
        try:
            self.client.storage \
                .from_(bucket) \
                .remove([file_path])

            logger.info(f"🗑️ Storage file deleted: {bucket}/{file_path}")
            return True

        except Exception as e:
            logger.error(f"❌ delete_file_from_storage error: {e}")
            return False


    # ==========================================
    # ✅ DOWNLOAD FILE FROM SUPABASE STORAGE
    # ==========================================
    def download_file_from_storage(
        self,
        bucket: str,
        file_path: str
    ) -> bytes:
        """
        Download file from Supabase Storage
        Returns file bytes
        """
        try:
            response = self.client.storage \
                .from_(bucket) \
                .download(file_path)

            logger.info(f"⬇️ File downloaded from storage: {bucket}/{file_path}")
            return response

        except Exception as e:
            logger.error(f"❌ download_file_from_storage error: {e}")
            raise


    # ==========================================
    # ✅ CREATE TABLES (CLI command)
    # ==========================================
    def create_tables(self):
        """
        Verify table exists by doing a test query.
        Actual table creation done via Supabase SQL Editor.
        """
        try:
            self.client \
                .table(self.table) \
                .select("id") \
                .limit(1) \
                .execute()

            logger.info(f"✅ Table '{self.table}' verified")

        except Exception as e:
            logger.error(
                f"❌ Table '{self.table}' not found. "
                f"Please run the SQL script in Supabase SQL Editor."
            )
            raise