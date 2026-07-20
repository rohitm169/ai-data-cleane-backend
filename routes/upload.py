"""
============================================
UPLOAD.PY — File Upload Route
POST /api/upload
============================================
"""

import os
import uuid
import logging
from datetime import datetime

import pandas as pd
from flask import Blueprint, request, jsonify, current_app

from config import Config
from utils.validators import validate_file
from services.file_handler import FileHandler

logger = logging.getLogger(__name__)


# ============================================
# ✅ BLUEPRINT
# ============================================
upload_bp = Blueprint('upload', __name__)


# ============================================
# ✅ POST /api/upload
# ============================================
@upload_bp.route('/upload', methods=['POST'])
def upload_file():
    """
    Upload CSV or Excel file.
    
    Request:
        - multipart/form-data
        - field name: 'file'
    
    Returns:
        - job_id, file_name, rows, cols, size, columns
    """
    try:
        # ─────────────────────────────────
        # Step 1: Check if file exists
        # ─────────────────────────────────
        if 'file' not in request.files:
            return jsonify({
                'success': False,
                'message': 'No file provided. Please upload a CSV or Excel file.',
                'error': 'missing_file',
            }), 400

        file = request.files['file']

        if file.filename == '' or file.filename is None:
            return jsonify({
                'success': False,
                'message': 'No file selected.',
                'error': 'empty_filename',
            }), 400

        # ─────────────────────────────────
        # Step 2: Validate file
        # ─────────────────────────────────
        validation = validate_file(file)

        if not validation['valid']:
            return jsonify({
                'success': False,
                'message': validation['message'],
                'error': validation.get('error', 'validation_failed'),
            }), 400

        # ─────────────────────────────────
        # Step 3: Generate unique filename
        # ─────────────────────────────────
        original_name = file.filename
        file_ext = original_name.rsplit('.', 1)[1].lower()
        unique_id = str(uuid.uuid4())[:8]
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        safe_name = f"{timestamp}_{unique_id}.{file_ext}"

        logger.info(f"📤 Uploading: {original_name} → {safe_name}")

        # ─────────────────────────────────
        # Step 4: Save file locally (temp)
        # ─────────────────────────────────
        local_path = os.path.join(Config.UPLOAD_FOLDER, safe_name)
        file.save(local_path)

        # Get file size
        file_size_bytes = os.path.getsize(local_path)
        file_size_str = FileHandler.format_file_size(file_size_bytes)

        logger.info(f"💾 Saved locally: {local_path} ({file_size_str})")

        # ─────────────────────────────────
        # Step 5: Read file to get info
        # ─────────────────────────────────
        try:
            df = FileHandler.read_file(local_path)
        except Exception as e:
            # Clean up local file
            FileHandler.delete_local_file(local_path)

            logger.error(f"❌ File read error: {e}")
            return jsonify({
                'success': False,
                'message': f'Could not read file: {str(e)}',
                'error': 'file_read_error',
            }), 422

        rows, cols = df.shape
        columns = df.columns.tolist()
        dtypes = {
            col: str(dtype)
            for col, dtype in df.dtypes.items()
        }

        logger.info(f"📊 File info: {rows} rows × {cols} cols")

        # ─────────────────────────────────
        # Step 6: Upload to Supabase Storage
        # ─────────────────────────────────
        storage_url = ""
        db = current_app.db

        if db:
            try:
                with open(local_path, 'rb') as f:
                    file_bytes = f.read()

                content_type = (
                    'text/csv' if file_ext == 'csv'
                    else 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                )

                storage_url = db.upload_file_to_storage(
                    bucket=Config.SUPABASE_UPLOAD_BUCKET,
                    file_path=safe_name,
                    file_data=file_bytes,
                    content_type=content_type,
                )

                logger.info(f"☁️ Uploaded to Supabase Storage")

            except Exception as e:
                logger.warning(f"⚠️ Storage upload failed: {e}")
                # Continue without storage — local file still exists

        # ─────────────────────────────────
        # Step 7: Create job in database
        # ─────────────────────────────────
        job_id = None

        if db:
            try:
                job = db.create_job({
                    'original_name': original_name,
                    'original_rows': rows,
                    'original_cols': cols,
                    'original_file_url': storage_url,
                    'file_size': file_size_str,
                    'file_type': file_ext,
                    'cleaning_options': {},
                })

                job_id = job.get('id')
                logger.info(f"✅ Job created in DB: {job_id}")

            except Exception as e:
                logger.warning(f"⚠️ DB job creation failed: {e}")
                # Generate local job ID
                job_id = str(uuid.uuid4())
        else:
            job_id = str(uuid.uuid4())

        # ─────────────────────────────────
        # Step 8: Store job info locally
        # ─────────────────────────────────
        # Save mapping: job_id → local file path
        FileHandler.save_job_mapping(job_id, {
            'local_path': local_path,
            'original_name': original_name,
            'safe_name': safe_name,
            'file_ext': file_ext,
            'file_size': file_size_str,
            'file_size_bytes': file_size_bytes,
            'rows': rows,
            'cols': cols,
            'columns': columns,
            'storage_url': storage_url,
        })

        # ─────────────────────────────────
        # Step 9: Return response
        # ─────────────────────────────────
        logger.info(f"✅ Upload complete: {original_name} → job_id: {job_id}")

        return jsonify({
            'success': True,
            'message': 'File uploaded successfully!',
            'job_id': job_id,
            'file_info': {
                'name': original_name,
                'size': file_size_str,
                'type': file_ext,
                'rows': rows,
                'cols': cols,
                'columns': columns,
                'dtypes': dtypes,
            },
        }), 200


    except Exception as e:
        logger.error(f"❌ Upload error: {e}")
        return jsonify({
            'success': False,
            'message': 'An unexpected error occurred during upload.',
            'error': str(e),
        }), 500


# ============================================
# ✅ GET /api/upload/info/<job_id>
# ============================================
@upload_bp.route('/upload/info/<job_id>', methods=['GET'])
def get_upload_info(job_id):
    """
    Get uploaded file info by job ID
    """
    try:
        # Try database
        db = current_app.db
        if db:
            job = db.get_job(job_id)
            if job:
                return jsonify({
                    'success': True,
                    'job_id': job_id,
                    'file_info': {
                        'name': job.get('original_name', ''),
                        'size': job.get('file_size', ''),
                        'type': job.get('file_type', ''),
                        'rows': job.get('original_rows', 0),
                        'cols': job.get('original_cols', 0),
                        'status': job.get('status', ''),
                    },
                }), 200

        # Try local mapping
        mapping = FileHandler.get_job_mapping(job_id)
        if mapping:
            return jsonify({
                'success': True,
                'job_id': job_id,
                'file_info': {
                    'name': mapping.get('original_name', ''),
                    'size': mapping.get('file_size', ''),
                    'type': mapping.get('file_ext', ''),
                    'rows': mapping.get('rows', 0),
                    'cols': mapping.get('cols', 0),
                    'columns': mapping.get('columns', []),
                    'status': 'uploaded',
                },
            }), 200

        return jsonify({
            'success': False,
            'message': 'Job not found.',
            'error': 'job_not_found',
        }), 404

    except Exception as e:
        logger.error(f"❌ get_upload_info error: {e}")
        return jsonify({
            'success': False,
            'message': 'Could not retrieve file info.',
            'error': str(e),
        }), 500


# ============================================
# ✅ DELETE /api/upload/<job_id>
# ============================================
@upload_bp.route('/upload/<job_id>', methods=['DELETE'])
def cancel_upload(job_id):
    """
    Cancel upload and delete file
    """
    try:
        db = current_app.db

        # Delete from storage
        if db:
            job = db.get_job(job_id)
            if job and job.get('original_file_url'):
                try:
                    # Extract file path from URL
                    safe_name = job['original_file_url'].split('/')[-1]
                    db.delete_file_from_storage(
                        Config.SUPABASE_UPLOAD_BUCKET,
                        safe_name
                    )
                except Exception as e:
                    logger.warning(f"⚠️ Storage delete failed: {e}")

            # Delete from database
            try:
                db.delete_job(job_id)
            except Exception as e:
                logger.warning(f"⚠️ DB delete failed: {e}")

        # Delete local file
        mapping = FileHandler.get_job_mapping(job_id)
        if mapping:
            local_path = mapping.get('local_path', '')
            FileHandler.delete_local_file(local_path)
            FileHandler.delete_job_mapping(job_id)

        logger.info(f"🗑️ Upload cancelled: {job_id}")

        return jsonify({
            'success': True,
            'message': 'Upload cancelled and file deleted.',
        }), 200

    except Exception as e:
        logger.error(f"❌ cancel_upload error: {e}")
        return jsonify({
            'success': False,
            'message': 'Could not cancel upload.',
            'error': str(e),
        }), 500