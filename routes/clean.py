"""
============================================
CLEAN.PY — Data Cleaning Route
POST /api/clean
GET  /api/clean/status/<job_id>
GET  /api/results/<job_id>
GET  /api/preview/<job_id>
GET  /api/report/<job_id>
============================================
"""

import os
import json
import logging
import threading
from datetime import datetime

import pandas as pd
from flask import Blueprint, request, jsonify, current_app

from config import Config
from services.cleaner import DataCleaner
from services.analyzer import DataAnalyzer
from services.file_handler import FileHandler

logger = logging.getLogger(__name__)


# ============================================
# ✅ BLUEPRINT
# ============================================
clean_bp = Blueprint('clean', __name__)


# ============================================
# ✅ IN-MEMORY JOB STATUS TRACKER
# ============================================
job_status_tracker = {}


# ============================================
# ✅ POST /api/clean
# ============================================
@clean_bp.route('/clean', methods=['POST'])
def start_cleaning():
    """
    Start AI data cleaning process.

    Request Body (JSON):
        {
            "job_id": "uuid",
            "options": {
                "remove_duplicates": true,
                "fill_missing": true,
                "fix_types": true,
                "standardize_text": true,
                "remove_outliers": false
            }
        }

    Returns:
        - status, message, job_id
    """
    try:
        # ─────────────────────────────────
        # Step 1: Parse request
        # ─────────────────────────────────
        data = request.get_json()

        if not data:
            return jsonify({
                'success': False,
                'message': 'Request body is required.',
                'error': 'missing_body',
            }), 400

        job_id = data.get('job_id')
        options = data.get('options', {})

        if not job_id:
            return jsonify({
                'success': False,
                'message': 'job_id is required.',
                'error': 'missing_job_id',
            }), 400

        # ─────────────────────────────────
        # Step 2: Get job info
        # ─────────────────────────────────
        mapping = FileHandler.get_job_mapping(job_id)

        if not mapping:
            return jsonify({
                'success': False,
                'message': 'Job not found. Please upload a file first.',
                'error': 'job_not_found',
            }), 404

        local_path = mapping.get('local_path', '')

        if not os.path.exists(local_path):
            return jsonify({
                'success': False,
                'message': 'Uploaded file not found. Please re-upload.',
                'error': 'file_not_found',
            }), 404

        # ─────────────────────────────────
        # Step 3: Check if already processing
        # ─────────────────────────────────
        if job_id in job_status_tracker:
            current_status = job_status_tracker[job_id].get('status')
            if current_status == 'processing':
                return jsonify({
                    'success': False,
                    'message': 'This job is already being processed.',
                    'error': 'already_processing',
                }), 409

        # ─────────────────────────────────
        # Step 4: Update status to processing
        # ─────────────────────────────────
        job_status_tracker[job_id] = {
            'status': 'processing',
            'progress': 0,
            'message': 'Starting cleaning process...',
            'started_at': datetime.utcnow().isoformat(),
        }

        # Update DB status
        db = current_app.db
        if db:
            try:
                db.update_status(job_id, Config.STATUS_PROCESSING)
                db.update_job(job_id, {
                    'cleaning_options': options,
                })
            except Exception as e:
                logger.warning(f"⚠️ DB status update failed: {e}")

        # ─────────────────────────────────
        # Step 5: Start cleaning in background
        # ─────────────────────────────────
        app = current_app._get_current_object()

        thread = threading.Thread(
            target=run_cleaning_job,
            args=(app, job_id, local_path, mapping, options),
            daemon=True,
        )
        thread.start()

        logger.info(f"🧹 Cleaning started: {job_id}")

        return jsonify({
            'success': True,
            'message': 'Cleaning started successfully!',
            'job_id': job_id,
            'status': 'processing',
        }), 200

    except Exception as e:
        logger.error(f"❌ start_cleaning error: {e}")
        return jsonify({
            'success': False,
            'message': 'Could not start cleaning process.',
            'error': str(e),
        }), 500


# ============================================
# ✅ BACKGROUND CLEANING JOB
# ============================================
def run_cleaning_job(app, job_id, local_path, mapping, options):
    """
    Run cleaning process in background thread.
    Updates job_status_tracker as it progresses.
    """
    with app.app_context():
        try:
            db = app.db

            # ─────────────────────────────
            # Phase 1: Read file
            # ─────────────────────────────
            update_job_status(job_id, 5, "Reading file...")
            df = FileHandler.read_file(local_path)
            original_rows, original_cols = df.shape

            logger.info(f"📖 File read: {original_rows} rows × {original_cols} cols")

            # ─────────────────────────────
            # Phase 2: Analyze data (before)
            # ─────────────────────────────
            update_job_status(job_id, 10, "Analyzing data structure...")
            analyzer = DataAnalyzer(df)
            before_analysis = analyzer.analyze()

            logger.info(f"🔍 Analysis complete")

            # ─────────────────────────────
            # Phase 3: Clean data
            # ─────────────────────────────
            cleaner = DataCleaner(df, options)

            # Step 3a: Remove duplicates
            if options.get('remove_duplicates', True):
                update_job_status(job_id, 20, "Removing duplicates...")
                cleaner.remove_duplicates()
                logger.info(f"🔄 Duplicates removed: {cleaner.stats['duplicates_removed']}")

            # Step 3b: Fill missing values
            if options.get('fill_missing', True):
                update_job_status(job_id, 35, "Filling missing values...")
                cleaner.fill_missing_values()
                logger.info(f"📝 Missing filled: {cleaner.stats['missing_filled']}")

            # Step 3c: Fix data types
            if options.get('fix_types', True):
                update_job_status(job_id, 50, "Fixing data types...")
                cleaner.fix_data_types()
                logger.info(f"🔧 Types fixed: {cleaner.stats['types_fixed']}")

            # Step 3d: Standardize text
            if options.get('standardize_text', True):
                update_job_status(job_id, 65, "Standardizing text...")
                cleaner.standardize_text()
                logger.info(f"✏️ Text standardized: {cleaner.stats['text_standardized']}")

            # Step 3e: Detect outliers
            if options.get('remove_outliers', False):
                update_job_status(job_id, 75, "Detecting outliers...")
                cleaner.detect_outliers()
                logger.info(f"📈 Outliers found: {cleaner.stats['outliers_found']}")

            # ─────────────────────────────
            # Phase 4: Get cleaned dataframe
            # ─────────────────────────────
            update_job_status(job_id, 80, "Preparing cleaned data...")
            cleaned_df = cleaner.get_cleaned_data()
            cleaned_rows, cleaned_cols = cleaned_df.shape

            # ─────────────────────────────
            # Phase 5: Analyze data (after)
            # ─────────────────────────────
            update_job_status(job_id, 85, "Analyzing cleaned data...")
            after_analyzer = DataAnalyzer(cleaned_df)
            after_analysis = after_analyzer.analyze()

            # ─────────────────────────────
            # Phase 6: Calculate quality score
            # ─────────────────────────────
            quality_score = cleaner.calculate_quality_score(
                before_analysis,
                after_analysis
            )

            # ─────────────────────────────
            # Phase 7: Save cleaned file
            # ─────────────────────────────
            update_job_status(job_id, 90, "Saving cleaned file...")

            original_name = mapping.get('original_name', 'data.csv')
            cleaned_filename = f"{Config.CLEANED_FILE_PREFIX}_{original_name}"

            if not cleaned_filename.endswith('.csv'):
                cleaned_filename = cleaned_filename.rsplit('.', 1)[0] + '.csv'

            cleaned_path = os.path.join(
                Config.CLEANED_FOLDER,
                cleaned_filename
            )

            cleaned_df.to_csv(cleaned_path, index=False)

            logger.info(f"💾 Cleaned file saved: {cleaned_path}")

            # ─────────────────────────────
            # Phase 8: Upload cleaned file
            # ─────────────────────────────
            cleaned_url = ""
            if db:
                try:
                    with open(cleaned_path, 'rb') as f:
                        cleaned_bytes = f.read()

                    cleaned_url = db.upload_file_to_storage(
                        bucket=Config.SUPABASE_CLEANED_BUCKET,
                        file_path=cleaned_filename,
                        file_data=cleaned_bytes,
                        content_type='text/csv',
                    )
                    logger.info(f"☁️ Cleaned file uploaded to storage")

                except Exception as e:
                    logger.warning(f"⚠️ Cleaned file storage upload failed: {e}")

            # ─────────────────────────────
            # Phase 9: Build report
            # ─────────────────────────────
            update_job_status(job_id, 95, "Generating report...")

            report_data = build_report(
                original_name=original_name,
                original_rows=original_rows,
                original_cols=original_cols,
                cleaned_rows=cleaned_rows,
                stats=cleaner.stats,
                cleaning_log=cleaner.get_cleaning_log(),
                before_analysis=before_analysis,
                after_analysis=after_analysis,
                quality_score=quality_score,
                column_profiles=after_analyzer.get_column_profiles(),
                changes=cleaner.get_changes_preview(),
            )

            # ─────────────────────────────
            # Phase 10: Save to database
            # ─────────────────────────────
            results = {
                'cleaned_rows': cleaned_rows,
                'duplicates_removed': cleaner.stats.get('duplicates_removed', 0),
                'missing_filled': cleaner.stats.get('missing_filled', 0),
                'types_fixed': cleaner.stats.get('types_fixed', 0),
                'text_standardized': cleaner.stats.get('text_standardized', 0),
                'outliers_found': cleaner.stats.get('outliers_found', 0),
                'quality_score': quality_score,
                'cleaned_file_url': cleaned_url,
                'report_data': report_data,
            }

            if db:
                try:
                    db.save_results(job_id, results)
                    logger.info(f"✅ Results saved to DB: {job_id}")
                except Exception as e:
                    logger.warning(f"⚠️ DB save results failed: {e}")

            # Save local results mapping
            FileHandler.save_job_mapping(job_id, {
                **mapping,
                'cleaned_path': cleaned_path,
                'cleaned_filename': cleaned_filename,
                'cleaned_url': cleaned_url,
                'results': results,
                'report_data': report_data,
                'status': 'completed',
            })

            # ─────────────────────────────
            # Phase 11: Complete!
            # ─────────────────────────────
            update_job_status(job_id, 100, "Cleaning completed!")
            job_status_tracker[job_id]['status'] = 'completed'
            job_status_tracker[job_id]['results'] = results

            logger.info(f"""
            ✅ Cleaning complete: {job_id}
            ├── Original:  {original_rows} rows
            ├── Cleaned:   {cleaned_rows} rows
            ├── Removed:   {cleaner.stats.get('duplicates_removed', 0)} duplicates
            ├── Filled:    {cleaner.stats.get('missing_filled', 0)} missing
            ├── Fixed:     {cleaner.stats.get('types_fixed', 0)} types
            ├── Text:      {cleaner.stats.get('text_standardized', 0)} standardized
            ├── Outliers:  {cleaner.stats.get('outliers_found', 0)} detected
            └── Score:     {quality_score}%
            """)

        except Exception as e:
            logger.error(f"❌ Cleaning job failed: {job_id} — {e}")

            job_status_tracker[job_id] = {
                'status': 'failed',
                'progress': 0,
                'message': str(e),
            }

            # Update DB
            if db:
                try:
                    db.update_status(
                        job_id,
                        Config.STATUS_FAILED,
                        str(e)
                    )
                except Exception:
                    pass


# ============================================
# ✅ UPDATE JOB STATUS HELPER
# ============================================
def update_job_status(job_id, progress, message):
    """Update in-memory status tracker"""
    job_status_tracker[job_id] = {
        **job_status_tracker.get(job_id, {}),
        'status': 'processing',
        'progress': progress,
        'message': message,
    }


# ============================================
# ✅ BUILD REPORT
# ============================================
def build_report(
    original_name,
    original_rows,
    original_cols,
    cleaned_rows,
    stats,
    cleaning_log,
    before_analysis,
    after_analysis,
    quality_score,
    column_profiles,
    changes,
):
    """Build complete cleaning report data"""

    total_issues = (
        stats.get('duplicates_removed', 0) +
        stats.get('missing_filled', 0) +
        stats.get('types_fixed', 0) +
        stats.get('text_standardized', 0)
    )

    return {
        'file_name': original_name,
        'cleaned_at': datetime.utcnow().isoformat(),
        'quality_score': quality_score,

        'stats': {
            'total_rows': original_rows,
            'total_cols': original_cols,
            'cleaned_rows': cleaned_rows,
            'cleaned_cells': total_issues,
            'rows_removed': original_rows - cleaned_rows,
            'missing_filled': stats.get('missing_filled', 0),
            'types_fixed': stats.get('types_fixed', 0),
            'text_standardized': stats.get('text_standardized', 0),
            'outliers_found': stats.get('outliers_found', 0),
            'final_rows': cleaned_rows,
        },

        'issues_breakdown': {
            'duplicates': stats.get('duplicates_removed', 0),
            'missing_values': stats.get('missing_filled', 0),
            'type_errors': stats.get('types_fixed', 0),
            'text_issues': stats.get('text_standardized', 0),
            'outliers': stats.get('outliers_found', 0),
            'format_issues': stats.get('format_fixed', 0),
        },

        'before_after': {
            'labels': [
                'Duplicates', 'Missing',
                'Type Errors', 'Text Issues', 'Outliers'
            ],
            'before': [
                stats.get('duplicates_removed', 0),
                stats.get('missing_filled', 0),
                stats.get('types_fixed', 0),
                stats.get('text_standardized', 0),
                stats.get('outliers_found', 0),
            ],
            'after': [0, 0, 0, 0, stats.get('outliers_found', 0)],
        },

        'column_issues': before_analysis.get('column_issues', {}),
        'cleaning_log': cleaning_log,
        'column_profiles': column_profiles,
        'changes_preview': changes,
    }


# ============================================
# ✅ GET /api/clean/status/<job_id>
# ============================================
@clean_bp.route('/clean/status/<job_id>', methods=['GET'])
def get_cleaning_status(job_id):
    """Check current cleaning job status"""
    try:
        # Check in-memory tracker
        if job_id in job_status_tracker:
            tracker = job_status_tracker[job_id]
            return jsonify({
                'success': True,
                'job_id': job_id,
                'status': tracker.get('status', 'unknown'),
                'progress': tracker.get('progress', 0),
                'message': tracker.get('message', ''),
            }), 200

        # Check database
        db = current_app.db
        if db:
            job = db.get_job(job_id)
            if job:
                return jsonify({
                    'success': True,
                    'job_id': job_id,
                    'status': job.get('status', 'unknown'),
                    'progress': (
                        100 if job.get('status') == 'completed'
                        else 0
                    ),
                    'message': job.get('error_message', ''),
                }), 200

        return jsonify({
            'success': False,
            'message': 'Job not found.',
            'error': 'job_not_found',
        }), 404

    except Exception as e:
        logger.error(f"❌ get_cleaning_status error: {e}")
        return jsonify({
            'success': False,
            'message': 'Could not get status.',
            'error': str(e),
        }), 500


# ============================================
# ✅ GET /api/results/<job_id>
# ============================================
@clean_bp.route('/results/<job_id>', methods=['GET'])
def get_results(job_id):
    """Get complete cleaning results"""
    try:
        # Check in-memory
        if job_id in job_status_tracker:
            tracker = job_status_tracker[job_id]
            if tracker.get('status') == 'completed':
                # Get report from local mapping
                mapping = FileHandler.get_job_mapping(job_id)
                if mapping and 'report_data' in mapping:
                    return jsonify({
                        'success': True,
                        'job_id': job_id,
                        **mapping['report_data'],
                    }), 200

        # Check database
        db = current_app.db
        if db:
            job = db.get_job(job_id)
            if job:
                if job.get('status') != Config.STATUS_COMPLETED:
                    return jsonify({
                        'success': False,
                        'message': f"Job is still {job.get('status', 'pending')}.",
                        'status': job.get('status'),
                    }), 202

                report = job.get('report_data', {})
                return jsonify({
                    'success': True,
                    'job_id': job_id,
                    **report,
                }), 200

        return jsonify({
            'success': False,
            'message': 'Results not found.',
            'error': 'results_not_found',
        }), 404

    except Exception as e:
        logger.error(f"❌ get_results error: {e}")
        return jsonify({
            'success': False,
            'message': 'Could not retrieve results.',
            'error': str(e),
        }), 500


# ============================================
# ✅ GET /api/preview/<job_id>
# ============================================
@clean_bp.route('/preview/<job_id>', methods=['GET'])
def get_preview(job_id):
    """
    Get data preview (before / after / changes)
    Query params: type=before|after|changes, page=1, limit=20
    """
    try:
        preview_type = request.args.get('type', 'before')
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', Config.PREVIEW_ROWS))

        mapping = FileHandler.get_job_mapping(job_id)

        if not mapping:
            return jsonify({
                'success': False,
                'message': 'Job not found.',
            }), 404

        # ── Before Preview ──
        if preview_type == 'before':
            local_path = mapping.get('local_path', '')
            if not os.path.exists(local_path):
                return jsonify({
                    'success': False,
                    'message': 'Original file not found.',
                }), 404

            df = FileHandler.read_file(local_path)
            start = (page - 1) * limit
            end = start + limit
            slice_df = df.iloc[start:end]

            return jsonify({
                'success': True,
                'type': 'before',
                'rows': slice_df.to_dict(orient='records'),
                'columns': df.columns.tolist(),
                'total_rows': len(df),
                'page': page,
                'limit': limit,
            }), 200

        # ── After Preview ──
        elif preview_type == 'after':
            cleaned_path = mapping.get('cleaned_path', '')
            if not cleaned_path or not os.path.exists(cleaned_path):
                return jsonify({
                    'success': False,
                    'message': 'Cleaned file not found.',
                }), 404

            df = pd.read_csv(cleaned_path)
            start = (page - 1) * limit
            end = start + limit
            slice_df = df.iloc[start:end]

            return jsonify({
                'success': True,
                'type': 'after',
                'rows': slice_df.to_dict(orient='records'),
                'columns': df.columns.tolist(),
                'total_rows': len(df),
                'page': page,
                'limit': limit,
            }), 200

        # ── Changes Preview ──
        elif preview_type == 'changes':
            report_data = mapping.get('report_data', {})
            changes = report_data.get('changes_preview', [])

            start = (page - 1) * limit
            end = start + limit
            paged_changes = changes[start:end]

            return jsonify({
                'success': True,
                'type': 'changes',
                'changes': paged_changes,
                'total_changes': len(changes),
                'page': page,
                'limit': limit,
            }), 200

        else:
            return jsonify({
                'success': False,
                'message': 'Invalid preview type. Use: before, after, changes',
            }), 400

    except Exception as e:
        logger.error(f"❌ get_preview error: {e}")
        return jsonify({
            'success': False,
            'message': 'Could not generate preview.',
            'error': str(e),
        }), 500


# ============================================
# ✅ GET /api/report/<job_id>
# ============================================
@clean_bp.route('/report/<job_id>', methods=['GET'])
def get_report(job_id):
    """Get detailed cleaning report"""
    try:
        # Local mapping
        mapping = FileHandler.get_job_mapping(job_id)
        if mapping and 'report_data' in mapping:
            return jsonify({
                'success': True,
                'job_id': job_id,
                'report': mapping['report_data'],
            }), 200

        # Database
        db = current_app.db
        if db:
            job = db.get_job(job_id)
            if job and job.get('report_data'):
                return jsonify({
                    'success': True,
                    'job_id': job_id,
                    'report': job['report_data'],
                }), 200

        return jsonify({
            'success': False,
            'message': 'Report not found.',
        }), 404

    except Exception as e:
        logger.error(f"❌ get_report error: {e}")
        return jsonify({
            'success': False,
            'message': 'Could not retrieve report.',
            'error': str(e),
        }), 500


# ============================================
# ✅ GET /api/report/<job_id>/download
# ============================================
@clean_bp.route('/report/<job_id>/download', methods=['GET'])
def download_report(job_id):
    """Download report as JSON file"""
    try:
        fmt = request.args.get('format', 'json')

        # Get report data
        mapping = FileHandler.get_job_mapping(job_id)
        report_data = None

        if mapping and 'report_data' in mapping:
            report_data = mapping['report_data']
        else:
            db = current_app.db
            if db:
                job = db.get_job(job_id)
                if job:
                    report_data = job.get('report_data', {})

        if not report_data:
            return jsonify({
                'success': False,
                'message': 'Report not found.',
            }), 404

        if fmt == 'json':
            # Save report JSON
            report_filename = f"{Config.REPORT_FILE_PREFIX}_{job_id[:8]}.json"
            report_path = os.path.join(Config.REPORTS_FOLDER, report_filename)

            os.makedirs(Config.REPORTS_FOLDER, exist_ok=True)

            with open(report_path, 'w') as f:
                json.dump(report_data, f, indent=Config.EXPORT_JSON_INDENT, default=str)

            from flask import send_file
            return send_file(
                report_path,
                mimetype='application/json',
                as_attachment=True,
                download_name=report_filename,
            )

        return jsonify({
            'success': False,
            'message': f'Format "{fmt}" is not supported. Use: json',
        }), 400

    except Exception as e:
        logger.error(f"❌ download_report error: {e}")
        return jsonify({
            'success': False,
            'message': 'Could not download report.',
            'error': str(e),
        }), 500