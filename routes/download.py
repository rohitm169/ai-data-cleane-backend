"""
============================================
DOWNLOAD.PY — File Download Route
GET /api/download/<job_id>
GET /api/download/url/<job_id>
============================================
"""

import os
import logging

from flask import (
    Blueprint,
    request,
    jsonify,
    current_app,
    send_file,
)

from config import Config
from services.file_handler import FileHandler

logger = logging.getLogger(__name__)


# ============================================
# ✅ BLUEPRINT
# ============================================
download_bp = Blueprint('download', __name__)


# ============================================
# ✅ GET /api/download/<job_id>
# ============================================
@download_bp.route('/download/<job_id>', methods=['GET'])
def download_cleaned_file(job_id):
    """
    Download the cleaned CSV file.
    Query Params:
        - type: 'cleaned' (default) | 'original'
    """
    try:
        file_type = request.args.get('type', 'cleaned')

        # ─────────────────────────────────
        # Step 1: Get job info
        # ─────────────────────────────────
        mapping = FileHandler.get_job_mapping(job_id)
        db = current_app.db
        job_data = None

        if db:
            try:
                job_data = db.get_job(job_id)
            except Exception as e:
                logger.warning(f"⚠️ DB fetch failed: {e}")

        # ─────────────────────────────────
        # Step 2: Check if job exists
        # ─────────────────────────────────
        if not mapping and not job_data:
            return jsonify({
                'success': False,
                'message': 'Job not found.',
                'error': 'job_not_found',
            }), 404

        # ─────────────────────────────────
        # Step 3: Check status
        # ─────────────────────────────────
        status = None
        if job_data:
            status = job_data.get('status')
        elif mapping:
            status = mapping.get('status')

        if file_type == 'cleaned' and status != 'completed':
            return jsonify({
                'success': False,
                'message': f'Cleaning not complete. Status: {status}',
                'status': status,
                'error': 'not_ready',
            }), 202

        # ─────────────────────────────────
        # Step 4: Determine file path
        # ─────────────────────────────────
        if file_type == 'original':
            file_path = get_original_path(mapping, job_data, db)
            original_name = get_original_name(mapping, job_data)
            download_name = original_name
        else:
            file_path = get_cleaned_path(mapping, job_data, db)
            original_name = get_original_name(mapping, job_data)
            download_name = f"{Config.CLEANED_FILE_PREFIX}_{original_name}"

            if not download_name.endswith('.csv'):
                download_name = download_name.rsplit('.', 1)[0] + '.csv'

        # ─────────────────────────────────
        # Step 5: Validate file exists
        # ─────────────────────────────────
        if not file_path or not os.path.exists(file_path):
            file_path = try_download_from_storage(
                job_id, file_type, mapping, job_data, db
            )

            if not file_path:
                return jsonify({
                    'success': False,
                    'message': 'File not found on server.',
                    'error': 'file_not_found',
                }), 404

        # ─────────────────────────────────
        # Step 6: Send file
        # ─────────────────────────────────
        logger.info(
            f"📥 Downloading: {download_name} "
            f"(job: {job_id}, type: {file_type})"
        )

        return send_file(
            file_path,
            mimetype='text/csv',
            as_attachment=True,
            download_name=download_name,
        )

    except Exception as e:
        logger.error(f"❌ download error: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'message': 'Could not download file.',
            'error': str(e),
        }), 500


# ============================================
# ✅ GET /api/download/url/<job_id>
# ============================================
@download_bp.route('/download/url/<job_id>', methods=['GET'])
def get_download_url(job_id):
    """Get download URL from Supabase Storage"""
    try:
        file_type = request.args.get('type', 'cleaned')

        db = current_app.db
        job_data = None
        mapping = FileHandler.get_job_mapping(job_id)

        if db:
            try:
                job_data = db.get_job(job_id)
            except Exception:
                pass

        if not mapping and not job_data:
            return jsonify({
                'success': False,
                'message': 'Job not found.',
            }), 404

        # Get URL
        download_url = ""

        if file_type == 'original':
            if job_data:
                download_url = job_data.get('original_file_url', '')
            elif mapping:
                download_url = mapping.get('storage_url', '')
        else:
            if job_data:
                download_url = job_data.get('cleaned_file_url', '')
            elif mapping:
                download_url = mapping.get('cleaned_url', '')

        if not download_url:
            return jsonify({
                'success': False,
                'message': 'URL not available. Use direct download.',
                'fallback': f'/api/download/{job_id}?type={file_type}',
            }), 404

        original_name = get_original_name(mapping, job_data)

        if file_type == 'cleaned':
            file_name = f"{Config.CLEANED_FILE_PREFIX}_{original_name}"
            if not file_name.endswith('.csv'):
                file_name = file_name.rsplit('.', 1)[0] + '.csv'
        else:
            file_name = original_name

        return jsonify({
            'success': True,
            'job_id': job_id,
            'type': file_type,
            'download_url': download_url,
            'file_name': file_name,
        }), 200

    except Exception as e:
        logger.error(f"❌ get_download_url error: {e}")
        return jsonify({
            'success': False,
            'message': 'Could not get download URL.',
            'error': str(e),
        }), 500


# ============================================
# ✅ GET /api/download/both/<job_id>
# ============================================
@download_bp.route('/download/both/<job_id>', methods=['GET'])
def download_both_urls(job_id):
    """Get both original and cleaned URLs"""
    try:
        db = current_app.db
        job_data = None
        mapping = FileHandler.get_job_mapping(job_id)

        if db:
            try:
                job_data = db.get_job(job_id)
            except Exception:
                pass

        if not mapping and not job_data:
            return jsonify({
                'success': False,
                'message': 'Job not found.',
            }), 404

        original_name = get_original_name(mapping, job_data)

        cleaned_name = f"{Config.CLEANED_FILE_PREFIX}_{original_name}"
        if not cleaned_name.endswith('.csv'):
            cleaned_name = cleaned_name.rsplit('.', 1)[0] + '.csv'

        original_url = ""
        cleaned_url = ""

        if job_data:
            original_url = job_data.get('original_file_url', '')
            cleaned_url = job_data.get('cleaned_file_url', '')
        elif mapping:
            original_url = mapping.get('storage_url', '')
            cleaned_url = mapping.get('cleaned_url', '')

        return jsonify({
            'success': True,
            'job_id': job_id,
            'original': {
                'name': original_name,
                'url': original_url,
                'download': f'/api/download/{job_id}?type=original',
            },
            'cleaned': {
                'name': cleaned_name,
                'url': cleaned_url,
                'download': f'/api/download/{job_id}?type=cleaned',
            },
        }), 200

    except Exception as e:
        logger.error(f"❌ download_both_urls error: {e}")
        return jsonify({
            'success': False,
            'message': 'Could not get download URLs.',
            'error': str(e),
        }), 500


# ============================================
# ✅ HELPER FUNCTIONS
# ============================================

def get_original_name(mapping, job_data):
    """Get original file name from mapping or DB"""
    if mapping and mapping.get('original_name'):
        return mapping.get('original_name')
    if job_data and job_data.get('original_name'):
        return job_data.get('original_name')
    return 'data.csv'


def get_original_path(mapping, job_data, db):
    """Find original file path from local"""
    if mapping:
        path = mapping.get('local_path', '')
        if path and os.path.exists(path):
            return path
    return None


def get_cleaned_path(mapping, job_data, db):
    """Find cleaned file path from local"""
    if mapping:
        path = mapping.get('cleaned_path', '')
        if path and os.path.exists(path):
            return path
    return None


def try_download_from_storage(job_id, file_type, mapping, job_data, db):
    """
    If local file missing, download from Supabase Storage
    and save locally. Returns local path or None.
    """
    if not db:
        return None

    try:
        if file_type == 'original':
            bucket = Config.SUPABASE_UPLOAD_BUCKET
            storage_url = (
                job_data.get('original_file_url', '') if job_data
                else mapping.get('storage_url', '') if mapping
                else ''
            )
        else:
            bucket = Config.SUPABASE_CLEANED_BUCKET
            storage_url = (
                job_data.get('cleaned_file_url', '') if job_data
                else mapping.get('cleaned_url', '') if mapping
                else ''
            )

        if not storage_url:
            return None

        file_name = storage_url.split('/')[-1].split('?')[0]

        if not file_name:
            return None

        file_bytes = db.download_file_from_storage(bucket, file_name)

        if not file_bytes:
            return None

        if file_type == 'original':
            local_dir = Config.UPLOAD_FOLDER
        else:
            local_dir = Config.CLEANED_FOLDER

        os.makedirs(local_dir, exist_ok=True)
        local_path = os.path.join(local_dir, file_name)

        with open(local_path, 'wb') as f:
            f.write(file_bytes)

        logger.info(
            f"⬇️ Downloaded from storage: {bucket}/{file_name}"
        )

        return local_path

    except Exception as e:
        logger.error(f"❌ Storage download failed: {e}")
        return None