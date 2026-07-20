"""
============================================
HISTORY.PY — Cleaning Job History Routes
GET    /api/history
GET    /api/history/stats
GET    /api/history/<job_id>
DELETE /api/history/<job_id>
DELETE /api/history/bulk-delete
============================================
"""

import logging

from flask import Blueprint, request, jsonify, current_app

from config import Config
from services.file_handler import FileHandler

logger = logging.getLogger(__name__)


# ============================================
# ✅ BLUEPRINT
# ============================================
history_bp = Blueprint('history', __name__)


# ============================================
# ✅ GET /api/history
# ============================================
@history_bp.route('/history', methods=['GET'])
def get_history():
    """
    Get paginated list of all cleaning jobs.

    Query Params:
        - page        : int  (default 1)
        - limit       : int  (default 10)
        - search      : str  (file name search)
        - date_filter : str  (all/today/week/month)
        - score_filter: str  (all/excellent/good/fair/poor)
        - sort        : str  (newest/oldest/score-high/score-low/rows-high)

    Returns:
        - { jobs, total, page, limit, pages }
    """
    try:
        # ─────────────────────────────────
        # Parse query params
        # ─────────────────────────────────
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', Config.HISTORY_PAGE_SIZE))
        search = request.args.get('search', '').strip()
        date_filter = request.args.get('date_filter', 'all')
        score_filter = request.args.get('score_filter', 'all')
        sort = request.args.get('sort', 'newest')

        # Validate page and limit
        if page < 1:
            page = 1
        if limit < 1 or limit > 100:
            limit = Config.HISTORY_PAGE_SIZE

        # ─────────────────────────────────
        # Validate filter values
        # ─────────────────────────────────
        valid_date_filters = ['all', 'today', 'week', 'month']
        valid_score_filters = ['all', 'excellent', 'good', 'fair', 'poor']
        valid_sorts = [
            'newest', 'oldest',
            'score-high', 'score-low',
            'rows-high',
        ]

        if date_filter not in valid_date_filters:
            date_filter = 'all'

        if score_filter not in valid_score_filters:
            score_filter = 'all'

        if sort not in valid_sorts:
            sort = 'newest'

        # ─────────────────────────────────
        # Get from database
        # ─────────────────────────────────
        db = current_app.db

        if db:
            result = db.get_all_jobs(
                page=page,
                limit=limit,
                search=search,
                date_filter=date_filter,
                score_filter=score_filter,
                sort=sort,
            )

            # Format jobs for frontend
            formatted_jobs = [
                format_job(job) for job in result.get('jobs', [])
            ]

            return jsonify({
                'success': True,
                'jobs': formatted_jobs,
                'total': result.get('total', 0),
                'page': result.get('page', page),
                'limit': result.get('limit', limit),
                'pages': result.get('pages', 0),
            }), 200

        # ─────────────────────────────────
        # Fallback: local mapping
        # ─────────────────────────────────
        all_mappings = FileHandler.get_all_job_mappings()

        jobs = []
        for jid, mapping in all_mappings.items():
            jobs.append({
                'id': jid,
                'file_name': mapping.get('original_name', ''),
                'file_size': mapping.get('file_size', ''),
                'file_type': mapping.get('file_ext', ''),
                'total_rows': mapping.get('rows', 0),
                'issues_fixed': (
                    mapping.get('results', {})
                    .get('cleaned_cells', 0)
                ),
                'rows_removed': (
                    mapping.get('results', {})
                    .get('rows_removed', 0)
                ),
                'quality_score': (
                    mapping.get('results', {})
                    .get('quality_score', 0)
                ),
                'status': mapping.get('status', 'uploaded'),
                'date': mapping.get('created_at', ''),
            })

        # Sort by date
        jobs.sort(
            key=lambda x: x.get('date', ''),
            reverse=True
        )

        # Paginate
        total = len(jobs)
        start = (page - 1) * limit
        end = start + limit
        paged_jobs = jobs[start:end]

        return jsonify({
            'success': True,
            'jobs': paged_jobs,
            'total': total,
            'page': page,
            'limit': limit,
            'pages': (total + limit - 1) // limit if total else 0,
        }), 200

    except ValueError as e:
        logger.error(f"❌ get_history ValueError: {e}")
        return jsonify({
            'success': False,
            'message': 'Invalid query parameter value.',
            'error': str(e),
        }), 400

    except Exception as e:
        logger.error(f"❌ get_history error: {e}")
        return jsonify({
            'success': False,
            'message': 'Could not retrieve history.',
            'error': str(e),
        }), 500


# ============================================
# ✅ GET /api/history/stats
# ============================================
@history_bp.route('/history/stats', methods=['GET'])
def get_history_stats():
    """
    Get overview stats for history page.

    Returns:
        - total_jobs, total_rows, total_issues, avg_score
    """
    try:
        db = current_app.db

        if db:
            stats = db.get_stats()
            return jsonify({
                'success': True,
                'stats': stats,
                'total_jobs': stats.get('total_jobs', 0),
                'total_rows': stats.get('total_rows', 0),
                'total_issues': stats.get('total_issues', 0),
                'avg_score': stats.get('avg_score', 0),
            }), 200

        # ─────────────────────────────────
        # Fallback: calculate from local
        # ─────────────────────────────────
        all_mappings = FileHandler.get_all_job_mappings()

        completed = [
            m for m in all_mappings.values()
            if m.get('status') == 'completed'
        ]

        total_rows = sum(m.get('rows', 0) for m in completed)

        total_issues = sum(
            m.get('results', {}).get('cleaned_cells', 0)
            for m in completed
        )

        scores = [
            m.get('results', {}).get('quality_score', 0)
            for m in completed
            if m.get('results', {}).get('quality_score', 0) > 0
        ]

        avg_score = round(
            sum(scores) / len(scores), 1
        ) if scores else 0

        return jsonify({
            'success': True,
            'total_jobs': len(all_mappings),
            'total_rows': total_rows,
            'total_issues': total_issues,
            'avg_score': avg_score,
        }), 200

    except Exception as e:
        logger.error(f"❌ get_history_stats error: {e}")
        return jsonify({
            'success': False,
            'message': 'Could not retrieve stats.',
            'error': str(e),
        }), 500


# ============================================
# ✅ GET /api/history/<job_id>
# ============================================
@history_bp.route('/history/<job_id>', methods=['GET'])
def get_single_job(job_id):
    """
    Get single job details by ID.

    Returns:
        - Full job details + report data
    """
    try:
        db = current_app.db
        job_data = None

        # ─────────────────────────────────
        # Try database
        # ─────────────────────────────────
        if db:
            try:
                job_data = db.get_job(job_id)
            except Exception as e:
                logger.warning(f"⚠️ DB fetch failed: {e}")

        if job_data:
            return jsonify({
                'success': True,
                'job': format_job(job_data),
                'report': job_data.get('report_data', {}),
            }), 200

        # ─────────────────────────────────
        # Try local mapping
        # ─────────────────────────────────
        mapping = FileHandler.get_job_mapping(job_id)

        if mapping:
            return jsonify({
                'success': True,
                'job': {
                    'id': job_id,
                    'file_name': mapping.get('original_name', ''),
                    'file_size': mapping.get('file_size', ''),
                    'file_type': mapping.get('file_ext', ''),
                    'total_rows': mapping.get('rows', 0),
                    'status': mapping.get('status', 'uploaded'),
                    'quality_score': (
                        mapping.get('results', {})
                        .get('quality_score', 0)
                    ),
                },
                'report': mapping.get('report_data', {}),
            }), 200

        # ─────────────────────────────────
        # Not found
        # ─────────────────────────────────
        return jsonify({
            'success': False,
            'message': 'Job not found.',
            'error': 'job_not_found',
        }), 404

    except Exception as e:
        logger.error(f"❌ get_single_job error: {e}")
        return jsonify({
            'success': False,
            'message': 'Could not retrieve job.',
            'error': str(e),
        }), 500


# ============================================
# ✅ DELETE /api/history/<job_id>
# ============================================
@history_bp.route('/history/<job_id>', methods=['DELETE'])
def delete_job(job_id):
    """
    Delete a single cleaning job.
    Also deletes associated files from storage.
    """
    try:
        db = current_app.db
        job_data = None

        # ─────────────────────────────────
        # Get job data
        # ─────────────────────────────────
        if db:
            try:
                job_data = db.get_job(job_id)
            except Exception as e:
                logger.warning(f"⚠️ DB fetch failed: {e}")

        mapping = FileHandler.get_job_mapping(job_id)

        if not job_data and not mapping:
            return jsonify({
                'success': False,
                'message': 'Job not found.',
                'error': 'job_not_found',
            }), 404

        # ─────────────────────────────────
        # Delete from Supabase Storage
        # ─────────────────────────────────
        if db and job_data:
            # Delete original file
            original_url = job_data.get('original_file_url', '')
            if original_url:
                try:
                    original_name = original_url.split('/')[-1].split('?')[0]
                    db.delete_file_from_storage(
                        Config.SUPABASE_UPLOAD_BUCKET,
                        original_name,
                    )
                    logger.info(f"🗑️ Original file deleted from storage")
                except Exception as e:
                    logger.warning(f"⚠️ Original storage delete failed: {e}")

            # Delete cleaned file
            cleaned_url = job_data.get('cleaned_file_url', '')
            if cleaned_url:
                try:
                    cleaned_name = cleaned_url.split('/')[-1].split('?')[0]
                    db.delete_file_from_storage(
                        Config.SUPABASE_CLEANED_BUCKET,
                        cleaned_name,
                    )
                    logger.info(f"🗑️ Cleaned file deleted from storage")
                except Exception as e:
                    logger.warning(f"⚠️ Cleaned storage delete failed: {e}")

        # ─────────────────────────────────
        # Delete local files
        # ─────────────────────────────────
        if mapping:
            # Delete original local file
            local_path = mapping.get('local_path', '')
            FileHandler.delete_local_file(local_path)

            # Delete cleaned local file
            cleaned_path = mapping.get('cleaned_path', '')
            FileHandler.delete_local_file(cleaned_path)

            # Delete job mapping
            FileHandler.delete_job_mapping(job_id)

            logger.info(f"🗑️ Local files deleted for job: {job_id}")

        # ─────────────────────────────────
        # Delete from database
        # ─────────────────────────────────
        if db:
            try:
                db.delete_job(job_id)
                logger.info(f"🗑️ Job deleted from DB: {job_id}")
            except Exception as e:
                logger.warning(f"⚠️ DB delete failed: {e}")

        return jsonify({
            'success': True,
            'message': 'Job deleted successfully.',
            'job_id': job_id,
        }), 200

    except Exception as e:
        logger.error(f"❌ delete_job error: {e}")
        return jsonify({
            'success': False,
            'message': 'Could not delete job.',
            'error': str(e),
        }), 500


# ============================================
# ✅ DELETE /api/history/bulk-delete
# ============================================
@history_bp.route('/history/bulk-delete', methods=['DELETE'])
def bulk_delete_jobs():
    """
    Delete multiple cleaning jobs at once.

    Request Body (JSON):
        {
            "job_ids": ["id1", "id2", "id3"]
        }

    Returns:
        - { success, deleted_count, failed_ids }
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({
                'success': False,
                'message': 'Request body is required.',
                'error': 'missing_body',
            }), 400

        job_ids = data.get('job_ids', [])

        if not job_ids:
            return jsonify({
                'success': False,
                'message': 'job_ids array is required.',
                'error': 'missing_job_ids',
            }), 400

        if not isinstance(job_ids, list):
            return jsonify({
                'success': False,
                'message': 'job_ids must be an array.',
                'error': 'invalid_type',
            }), 400

        if len(job_ids) > 50:
            return jsonify({
                'success': False,
                'message': 'Maximum 50 jobs can be deleted at once.',
                'error': 'too_many_ids',
            }), 400

        # ─────────────────────────────────
        # Delete each job
        # ─────────────────────────────────
        deleted_count = 0
        failed_ids = []
        db = current_app.db

        for job_id in job_ids:
            try:
                # Delete local files
                mapping = FileHandler.get_job_mapping(job_id)
                if mapping:
                    FileHandler.delete_local_file(
                        mapping.get('local_path', '')
                    )
                    FileHandler.delete_local_file(
                        mapping.get('cleaned_path', '')
                    )
                    FileHandler.delete_job_mapping(job_id)

                # Delete storage files
                if db:
                    job_data = db.get_job(job_id)
                    if job_data:
                        # Original file
                        original_url = job_data.get('original_file_url', '')
                        if original_url:
                            original_name = (
                                original_url.split('/')[-1].split('?')[0]
                            )
                            try:
                                db.delete_file_from_storage(
                                    Config.SUPABASE_UPLOAD_BUCKET,
                                    original_name,
                                )
                            except Exception:
                                pass

                        # Cleaned file
                        cleaned_url = job_data.get('cleaned_file_url', '')
                        if cleaned_url:
                            cleaned_name = (
                                cleaned_url.split('/')[-1].split('?')[0]
                            )
                            try:
                                db.delete_file_from_storage(
                                    Config.SUPABASE_CLEANED_BUCKET,
                                    cleaned_name,
                                )
                            except Exception:
                                pass

                    # Delete from DB
                    db.delete_job(job_id)

                deleted_count += 1
                logger.info(f"🗑️ Bulk deleted job: {job_id}")

            except Exception as e:
                logger.error(f"❌ Failed to delete job {job_id}: {e}")
                failed_ids.append(job_id)

        # ─────────────────────────────────
        # Try bulk DB delete for remaining
        # ─────────────────────────────────
        if db and deleted_count > 0:
            try:
                valid_ids = [j for j in job_ids if j not in failed_ids]
                if valid_ids:
                    db.delete_multiple_jobs(valid_ids)
            except Exception as e:
                logger.warning(f"⚠️ Bulk DB delete failed: {e}")

        logger.info(
            f"🗑️ Bulk delete complete: "
            f"{deleted_count} deleted, {len(failed_ids)} failed"
        )

        return jsonify({
            'success': True,
            'message': f'{deleted_count} jobs deleted successfully.',
            'deleted_count': deleted_count,
            'failed_ids': failed_ids,
        }), 200

    except Exception as e:
        logger.error(f"❌ bulk_delete_jobs error: {e}")
        return jsonify({
            'success': False,
            'message': 'Could not delete jobs.',
            'error': str(e),
        }), 500


# ============================================
# ✅ FORMAT JOB HELPER
# ============================================
def format_job(job: dict) -> dict:
    """
    Format job data for frontend consumption.
    Renames DB fields to match frontend expectations.
    """
    if not job:
        return {}

    # Calculate issues fixed
    issues_fixed = (
        job.get('duplicates_removed', 0) +
        job.get('missing_filled', 0) +
        job.get('types_fixed', 0) +
        job.get('text_standardized', 0)
    )

    return {
        'id': job.get('id', ''),
        'file_name': job.get('original_name', ''),
        'file_size': job.get('file_size', ''),
        'file_type': job.get('file_type', 'csv'),
        'date': job.get('created_at', ''),
        'total_rows': job.get('original_rows', 0),
        'issues_fixed': issues_fixed,
        'rows_removed': job.get('duplicates_removed', 0),
        'quality_score': round(job.get('quality_score', 0), 1),
        'status': job.get('status', 'pending'),
        'error': job.get('error_message', ''),
        'original_url': job.get('original_file_url', ''),
        'cleaned_url': job.get('cleaned_file_url', ''),
        'cleaning_options': job.get('cleaning_options', {}),
        'updated_at': job.get('updated_at', ''),
    }