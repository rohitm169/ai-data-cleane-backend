"""
============================================
APP.PY — Main Flask Application
AI Data Cleaning Dashboard Backend
============================================
"""

import os
import logging
from datetime import datetime

from flask import Flask, jsonify, request
from flask_cors import CORS

# Import config
from config import Config

# Import route blueprints
from routes.upload import upload_bp
from routes.clean import clean_bp
from routes.download import download_bp
from routes.history import history_bp

# Import database
from models.database import Database


# ============================================
# ✅ LOGGING SETUP
# ============================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


# ============================================
# ✅ CREATE FLASK APP
# ============================================
def create_app():
    """Application Factory Pattern"""

    app = Flask(__name__)

    # ────────────────────────────────────────
    # Load Config
    # ────────────────────────────────────────
    app.config.from_object(Config)

    logger.info(f"🚀 Environment: {Config.FLASK_ENV}")
    logger.info(f"📁 Upload Folder: {Config.UPLOAD_FOLDER}")
    logger.info(f"📁 Cleaned Folder: {Config.CLEANED_FOLDER}")

    # ────────────────────────────────────────
    # CORS Setup (Allow frontend to call API)
    # ────────────────────────────────────────
    CORS(app, resources={
        r"/api/*": {
            "origins": Config.ALLOWED_ORIGINS,
            "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            "allow_headers": [
                "Content-Type",
                "Authorization",
                "Accept",
                "X-Requested-With",
            ],
            "expose_headers": [
                "Content-Disposition",
                "Content-Length",
            ],
            "supports_credentials": False,
            "max_age": 600,
        }
    })

    # ────────────────────────────────────────
    # Create Required Directories
    # ────────────────────────────────────────
    os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)
    os.makedirs(Config.CLEANED_FOLDER, exist_ok=True)

    logger.info("📂 Directories created/verified")

    # ────────────────────────────────────────
    # Initialize Database (Supabase)
    # ────────────────────────────────────────
    try:
        db = Database()
        app.db = db
        logger.info("✅ Supabase connected successfully")
    except Exception as e:
        logger.error(f"❌ Supabase connection failed: {e}")
        app.db = None

    # ────────────────────────────────────────
    # Register Blueprints (Routes)
    # ────────────────────────────────────────
    app.register_blueprint(upload_bp, url_prefix='/api')
    app.register_blueprint(clean_bp, url_prefix='/api')
    app.register_blueprint(download_bp, url_prefix='/api')
    app.register_blueprint(history_bp, url_prefix='/api')

    logger.info("📌 All routes registered")

    # ────────────────────────────────────────
    # Health Check Route
    # ────────────────────────────────────────
    @app.route('/api/health', methods=['GET'])
    def health_check():
        """Server health check endpoint"""

        # Check Supabase
        db_status = 'connected'
        try:
            if app.db:
                app.db.health_check()
            else:
                db_status = 'disconnected'
        except Exception:
            db_status = 'error'

        return jsonify({
            'status': 'ok',
            'message': 'AI Data Cleaning API is running',
            'timestamp': datetime.utcnow().isoformat(),
            'version': '1.0.0',
            'database': db_status,
            'environment': Config.FLASK_ENV,
        }), 200

    # ────────────────────────────────────────
    # Root Route
    # ────────────────────────────────────────
    @app.route('/', methods=['GET'])
    def root():
        """API root info"""
        return jsonify({
            'name': 'AI Data Cleaning Dashboard API',
            'version': '1.0.0',
            'description': 'Upload CSV/Excel files and get AI-powered data cleaning',
            'endpoints': {
                'health': '/api/health',
                'upload': '/api/upload [POST]',
                'clean': '/api/clean [POST]',
                'results': '/api/results/<job_id> [GET]',
                'preview': '/api/preview/<job_id> [GET]',
                'download': '/api/download/<job_id> [GET]',
                'report': '/api/report/<job_id> [GET]',
                'history': '/api/history [GET]',
                'history_stats': '/api/history/stats [GET]',
            },
            'docs': 'https://github.com/your-repo/ai-data-cleaning-dashboard',
        }), 200

    # ────────────────────────────────────────
    # Error Handlers
    # ────────────────────────────────────────
    @app.errorhandler(400)
    def bad_request(error):
        return jsonify({
            'success': False,
            'error': 'Bad Request',
            'message': str(error.description) if hasattr(error, 'description') else 'Invalid request data.',
            'status': 400,
        }), 400

    @app.errorhandler(404)
    def not_found(error):
        return jsonify({
            'success': False,
            'error': 'Not Found',
            'message': 'The requested resource was not found.',
            'status': 404,
        }), 404

    @app.errorhandler(405)
    def method_not_allowed(error):
        return jsonify({
            'success': False,
            'error': 'Method Not Allowed',
            'message': f'Method {request.method} is not allowed for this endpoint.',
            'status': 405,
        }), 405

    @app.errorhandler(413)
    def file_too_large(error):
        return jsonify({
            'success': False,
            'error': 'File Too Large',
            'message': f'File exceeds maximum size of {Config.MAX_FILE_SIZE // (1024 * 1024)}MB.',
            'status': 413,
        }), 413

    @app.errorhandler(415)
    def unsupported_media(error):
        return jsonify({
            'success': False,
            'error': 'Unsupported File Type',
            'message': 'Only CSV, XLSX, and XLS files are supported.',
            'status': 415,
        }), 415

    @app.errorhandler(422)
    def unprocessable(error):
        return jsonify({
            'success': False,
            'error': 'Unprocessable Entity',
            'message': str(error.description) if hasattr(error, 'description') else 'Could not process the request.',
            'status': 422,
        }), 422

    @app.errorhandler(429)
    def too_many_requests(error):
        return jsonify({
            'success': False,
            'error': 'Too Many Requests',
            'message': 'Rate limit exceeded. Please try again later.',
            'status': 429,
        }), 429

    @app.errorhandler(500)
    def internal_error(error):
        logger.error(f"Internal Server Error: {error}")
        return jsonify({
            'success': False,
            'error': 'Internal Server Error',
            'message': 'An unexpected error occurred. Please try again later.',
            'status': 500,
        }), 500

    # ────────────────────────────────────────
    # Before Request Hook
    # ────────────────────────────────────────
    @app.before_request
    def before_request():
        """Runs before every request"""

        # Log incoming requests
        if request.path != '/api/health':
            logger.info(
                f"📨 {request.method} {request.path} "
                f"— IP: {request.remote_addr}"
            )

    # ────────────────────────────────────────
    # After Request Hook
    # ────────────────────────────────────────
    @app.after_request
    def after_request(response):
        """Runs after every request"""

        # Add common response headers
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        response.headers['X-API-Version'] = '1.0.0'

        # Log response status
        if request.path != '/api/health':
            logger.info(
                f"📤 {request.method} {request.path} "
                f"→ {response.status_code}"
            )

        return response

    # ────────────────────────────────────────
    # Teardown Hook (Cleanup)
    # ────────────────────────────────────────
    @app.teardown_appcontext
    def cleanup(exception=None):
        """Cleanup after request context"""
        if exception:
            logger.error(f"Request error: {exception}")

    # ────────────────────────────────────────
    # CLI Commands (optional)
    # ────────────────────────────────────────
    @app.cli.command('init-db')
    def init_db_command():
        """Initialize database tables"""
        try:
            if app.db:
                app.db.create_tables()
                logger.info("✅ Database tables created")
            else:
                logger.error("❌ No database connection")
        except Exception as e:
            logger.error(f"❌ Failed to initialize DB: {e}")

    @app.cli.command('cleanup')
    def cleanup_command():
        """Clean up old temporary files"""
        import shutil
        try:
            # Clean upload folder
            if os.path.exists(Config.UPLOAD_FOLDER):
                shutil.rmtree(Config.UPLOAD_FOLDER)
                os.makedirs(Config.UPLOAD_FOLDER)
                logger.info("🧹 Upload folder cleaned")

            # Clean cleaned folder
            if os.path.exists(Config.CLEANED_FOLDER):
                shutil.rmtree(Config.CLEANED_FOLDER)
                os.makedirs(Config.CLEANED_FOLDER)
                logger.info("🧹 Cleaned folder cleaned")

        except Exception as e:
            logger.error(f"❌ Cleanup failed: {e}")

    return app


# ============================================
# ✅ CREATE APP INSTANCE
# ============================================
app = create_app()


# ============================================
# ✅ RUN SERVER
# ============================================
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))

    logger.info(f"""
    ╔══════════════════════════════════════════╗
    ║   🧠 AI Data Cleaning Dashboard API     ║
    ║   Running on http://localhost:{port}       ║
    ║   Environment: {Config.FLASK_ENV:<24s}║
    ║   Press CTRL+C to quit                   ║
    ╚══════════════════════════════════════════╝
    """)

    app.run(
        host='0.0.0.0',
        port=port,
        debug=Config.DEBUG,
    )