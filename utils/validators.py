"""
============================================
VALIDATORS.PY — File Validation Logic
Validate uploaded files before processing
============================================
"""

import os
import logging
from pathlib import Path
from typing import Optional

from config import Config

logger = logging.getLogger(__name__)


# ============================================
# ✅ MAIN VALIDATE FILE FUNCTION
# ============================================
def validate_file(file) -> dict:
    """
    Validate uploaded file.
    Checks extension, size, mime type,
    filename safety and content.

    Args:
        file: Flask request.files object

    Returns:
        {
            valid   : bool,
            message : str,
            error   : str (error code)
        }
    """
    try:
        # ─────────────────────────────────
        # Check 1: File object exists
        # ─────────────────────────────────
        if file is None:
            return _fail(
                'No file provided.',
                'missing_file'
            )

        # ─────────────────────────────────
        # Check 2: Filename exists
        # ─────────────────────────────────
        filename = file.filename

        if not filename or filename.strip() == '':
            return _fail(
                'File has no name.',
                'empty_filename'
            )

        # ─────────────────────────────────
        # Check 3: Filename safety
        # ─────────────────────────────────
        safety = validate_filename(filename)
        if not safety['valid']:
            return safety

        # ─────────────────────────────────
        # Check 4: File extension
        # ─────────────────────────────────
        ext = validate_extension(filename)
        if not ext['valid']:
            return ext

        # ─────────────────────────────────
        # Check 5: MIME type
        # ─────────────────────────────────
        mime = validate_mime_type(file)
        if not mime['valid']:
            return mime

        # ─────────────────────────────────
        # Check 6: File size
        # ─────────────────────────────────
        size = validate_file_size(file)
        if not size['valid']:
            return size

        # ─────────────────────────────────
        # Check 7: File not empty
        # ─────────────────────────────────
        empty = validate_not_empty(file)
        if not empty['valid']:
            return empty

        # ─────────────────────────────────
        # All checks passed
        # ─────────────────────────────────
        logger.info(f"✅ File validated: {filename}")

        return _pass(f"File '{filename}' is valid.")

    except Exception as e:
        logger.error(f"❌ validate_file error: {e}")
        return _fail(
            'File validation failed unexpectedly.',
            'validation_error'
        )


# ============================================
# ✅ VALIDATE FILENAME SAFETY
# ============================================
def validate_filename(filename: str) -> dict:
    """
    Check filename for safety issues.
    - No path traversal (../)
    - No null bytes
    - No dangerous characters
    - Reasonable length
    """
    try:
        # Check null bytes
        if '\x00' in filename:
            return _fail(
                'Filename contains invalid characters.',
                'invalid_filename'
            )

        # Check path traversal
        if '..' in filename or '/' in filename or '\\' in filename:
            return _fail(
                'Filename contains invalid path characters.',
                'path_traversal'
            )

        # Check length
        if len(filename) > 255:
            return _fail(
                'Filename is too long. Maximum 255 characters.',
                'filename_too_long'
            )

        if len(filename) < 3:
            return _fail(
                'Filename is too short.',
                'filename_too_short'
            )

        # Check for dangerous extensions (double extension)
        dangerous = [
            '.php', '.js', '.py', '.sh', '.exe',
            '.bat', '.cmd', '.ps1', '.rb', '.pl',
        ]
        filename_lower = filename.lower()

        for danger in dangerous:
            if danger in filename_lower and not filename_lower.endswith(
                tuple(Config.ALLOWED_EXTENSIONS)
            ):
                return _fail(
                    'Filename contains dangerous extension.',
                    'dangerous_extension'
                )

        return _pass('Filename is safe.')

    except Exception as e:
        logger.error(f"❌ validate_filename error: {e}")
        return _fail('Filename validation failed.', 'filename_error')


# ============================================
# ✅ VALIDATE FILE EXTENSION
# ============================================
def validate_extension(filename: str) -> dict:
    """
    Check if file extension is allowed.
    Allowed: .csv, .xlsx, .xls
    """
    try:
        if '.' not in filename:
            return _fail(
                'File has no extension. '
                'Please upload a CSV or Excel file.',
                'no_extension'
            )

        ext = filename.rsplit('.', 1)[1].lower()

        if ext not in Config.ALLOWED_EXTENSIONS:
            allowed = ', '.join(
                f'.{e}' for e in Config.ALLOWED_EXTENSIONS
            )
            return _fail(
                f'File type ".{ext}" is not supported. '
                f'Allowed types: {allowed}',
                'invalid_extension'
            )

        return _pass(f'Extension ".{ext}" is allowed.')

    except Exception as e:
        logger.error(f"❌ validate_extension error: {e}")
        return _fail('Extension validation failed.', 'extension_error')


# ============================================
# ✅ VALIDATE MIME TYPE
# ============================================
def validate_mime_type(file) -> dict:
    """
    Check if file MIME type is allowed.
    Note: MIME type can be spoofed,
    so this is a secondary check only.
    """
    try:
        content_type = getattr(file, 'content_type', None)
        mimetype = getattr(file, 'mimetype', None)

        mime = content_type or mimetype or ''

        # If no mime type provided, skip check
        if not mime:
            return _pass('MIME type not provided, skipping check.')

        if mime in Config.ALLOWED_MIME_TYPES:
            return _pass(f'MIME type "{mime}" is allowed.')

        # Some browsers send generic types — allow them
        generic_allowed = [
            'application/octet-stream',
            'binary/octet-stream',
            'application/zip',
        ]

        if mime in generic_allowed:
            return _pass(f'Generic MIME type "{mime}" accepted.')

        # Warn but don't block
        logger.warning(
            f"⚠️ Unexpected MIME type: {mime} — allowing with warning"
        )

        return _pass(f'MIME type "{mime}" accepted with warning.')

    except Exception as e:
        logger.error(f"❌ validate_mime_type error: {e}")
        return _pass('MIME type check skipped.')


# ============================================
# ✅ VALIDATE FILE SIZE
# ============================================
def validate_file_size(file) -> dict:
    """
    Check if file size is within limits.
    Max size defined in Config.MAX_FILE_SIZE
    """
    try:
        # Get file size
        file.seek(0, 2)  # Seek to end
        file_size = file.tell()
        file.seek(0)     # Reset to start

        max_size = Config.MAX_FILE_SIZE
        max_size_mb = max_size / (1024 * 1024)

        if file_size == 0:
            return _fail(
                'File is empty (0 bytes).',
                'empty_file'
            )

        if file_size > max_size:
            actual_mb = file_size / (1024 * 1024)
            return _fail(
                f'File too large ({actual_mb:.1f} MB). '
                f'Maximum allowed size is {max_size_mb:.0f} MB.',
                'file_too_large'
            )

        logger.info(
            f"📏 File size: "
            f"{file_size / (1024 * 1024):.2f} MB ✅"
        )

        return _pass(
            f'File size {file_size / (1024 * 1024):.1f} MB is valid.'
        )

    except Exception as e:
        logger.error(f"❌ validate_file_size error: {e}")
        return _fail('File size validation failed.', 'size_error')


# ============================================
# ✅ VALIDATE FILE NOT EMPTY
# ============================================
def validate_not_empty(file) -> dict:
    """
    Check if file has actual content.
    Reads first chunk to verify data exists.
    """
    try:
        file.seek(0)
        chunk = file.read(512)
        file.seek(0)

        if not chunk:
            return _fail(
                'File appears to be empty.',
                'empty_content'
            )

        # Check for common empty file patterns
        content = chunk.decode('utf-8', errors='ignore').strip()

        if len(content) == 0:
            return _fail(
                'File has no readable content.',
                'no_content'
            )

        return _pass('File has content.')

    except Exception as e:
        logger.error(f"❌ validate_not_empty error: {e}")
        return _pass('Content check skipped.')


# ============================================
# ✅ VALIDATE JOB ID
# ============================================
def validate_job_id(job_id: str) -> dict:
    """
    Validate job ID format.
    Must be non-empty string,
    reasonable length, safe characters.
    """
    try:
        if not job_id:
            return _fail(
                'Job ID is required.',
                'missing_job_id'
            )

        if not isinstance(job_id, str):
            return _fail(
                'Job ID must be a string.',
                'invalid_job_id_type'
            )

        # Length check
        if len(job_id) < 4:
            return _fail(
                'Job ID is too short.',
                'job_id_too_short'
            )

        if len(job_id) > 128:
            return _fail(
                'Job ID is too long.',
                'job_id_too_long'
            )

        # Safe characters only
        import re
        if not re.match(r'^[a-zA-Z0-9\-_]+$', job_id):
            return _fail(
                'Job ID contains invalid characters.',
                'invalid_job_id_chars'
            )

        return _pass('Job ID is valid.')

    except Exception as e:
        logger.error(f"❌ validate_job_id error: {e}")
        return _fail('Job ID validation failed.', 'job_id_error')


# ============================================
# ✅ VALIDATE CLEANING OPTIONS
# ============================================
def validate_cleaning_options(options: dict) -> dict:
    """
    Validate cleaning options dict.
    All values must be boolean.
    """
    try:
        if not options:
            return _pass('No options provided, using defaults.')

        if not isinstance(options, dict):
            return _fail(
                'Options must be a JSON object.',
                'invalid_options_type'
            )

        # Allowed option keys
        allowed_keys = {
            'remove_duplicates',
            'fill_missing',
            'fix_types',
            'standardize_text',
            'remove_outliers',
        }

        # Check for unknown keys
        unknown = set(options.keys()) - allowed_keys
        if unknown:
            logger.warning(
                f"⚠️ Unknown cleaning options: {unknown}"
            )

        # Validate all values are boolean
        for key, value in options.items():
            if key not in allowed_keys:
                continue

            if not isinstance(value, bool):
                return _fail(
                    f'Option "{key}" must be true or false.',
                    'invalid_option_value'
                )

        # Check at least one option is True
        active_options = [
            v for k, v in options.items()
            if k in allowed_keys and v is True
        ]

        if options and len(active_options) == 0:
            return _fail(
                'At least one cleaning option must be selected.',
                'no_options_selected'
            )

        return _pass('Cleaning options are valid.')

    except Exception as e:
        logger.error(f"❌ validate_cleaning_options error: {e}")
        return _fail(
            'Options validation failed.',
            'options_error'
        )


# ============================================
# ✅ VALIDATE PAGINATION PARAMS
# ============================================
def validate_pagination(
    page: Optional[int] = None,
    limit: Optional[int] = None,
    max_limit: int = 100,
) -> dict:
    """
    Validate pagination query parameters.

    Args:
        page      : Page number (min 1)
        limit     : Items per page (min 1, max 100)
        max_limit : Maximum allowed limit

    Returns:
        { valid, page, limit, message }
    """
    try:
        # Validate page
        if page is not None:
            if not isinstance(page, int) or page < 1:
                return _fail(
                    'Page must be a positive integer.',
                    'invalid_page'
                )

        # Validate limit
        if limit is not None:
            if not isinstance(limit, int) or limit < 1:
                return _fail(
                    'Limit must be a positive integer.',
                    'invalid_limit'
                )

            if limit > max_limit:
                return _fail(
                    f'Limit cannot exceed {max_limit}.',
                    'limit_too_large'
                )

        return {
            'valid': True,
            'message': 'Pagination params are valid.',
            'page': page or 1,
            'limit': limit or 10,
        }

    except Exception as e:
        logger.error(f"❌ validate_pagination error: {e}")
        return _fail('Pagination validation failed.', 'pagination_error')


# ============================================
# ✅ HELPER: Return Pass Result
# ============================================
def _pass(message: str = 'Valid.') -> dict:
    """Return successful validation result"""
    return {
        'valid': True,
        'message': message,
        'error': None,
    }


# ============================================
# ✅ HELPER: Return Fail Result
# ============================================
def _fail(message: str, error: str = 'validation_failed') -> dict:
    """Return failed validation result"""
    logger.warning(f"⚠️ Validation failed: {message} [{error}]")
    return {
        'valid': False,
        'message': message,
        'error': error,
    }