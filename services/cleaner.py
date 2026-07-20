"""
============================================
CLEANER.PY — AI Data Cleaning Engine
Core cleaning logic using Pandas
============================================
"""

import re
import logging
from datetime import datetime
from typing import Optional

import numpy as np
import pandas as pd

from config import Config

logger = logging.getLogger(__name__)


# ============================================
# ✅ DATA CLEANER CLASS
# ============================================
class DataCleaner:
    """
    AI-powered data cleaning engine.
    Handles duplicates, missing values,
    type fixing, text standardization,
    and outlier detection.
    """

    def __init__(self, df: pd.DataFrame, options: dict = None):
        """
        Initialize cleaner with dataframe and options.

        Args:
            df      : Original pandas DataFrame
            options : Cleaning options dict
        """
        self.original_df = df.copy()
        self.df = df.copy()
        self.options = options or {}

        # Stats tracker
        self.stats = {
            'duplicates_removed': 0,
            'missing_filled': 0,
            'types_fixed': 0,
            'text_standardized': 0,
            'outliers_found': 0,
            'format_fixed': 0,
        }

        # Cleaning log (steps)
        self.cleaning_log = []

        # Changes tracker (for preview)
        self.changes = []

        logger.info(
            f"🧹 DataCleaner initialized: "
            f"{df.shape[0]} rows × {df.shape[1]} cols"
        )


    # ==========================================
    # ✅ STEP 1: REMOVE DUPLICATES
    # ==========================================
    def remove_duplicates(self):
        """
        Remove exact duplicate rows.
        Keeps first occurrence.
        """
        try:
            before = len(self.df)

            # Find duplicate rows
            duplicate_mask = self.df.duplicated(keep='first')
            duplicate_count = duplicate_mask.sum()

            if duplicate_count > 0:
                # Track changes
                dup_rows = self.df[duplicate_mask]
                for idx in dup_rows.index[:5]:  # Preview first 5
                    self.changes.append({
                        'row': int(idx) + 1,
                        'column': '(entire row)',
                        'before': str(self.df.loc[idx].to_dict()),
                        'after': '—',
                        'action': 'Duplicate Removed',
                        'action_class': 'remove',
                    })

                # Remove duplicates
                self.df = self.df.drop_duplicates(keep='first')
                self.df = self.df.reset_index(drop=True)

            after = len(self.df)
            removed = before - after
            self.stats['duplicates_removed'] = removed

            # Log
            self._add_log(
                log_type='success' if removed > 0 else 'info',
                action=f"Removed {removed} duplicate rows",
                detail=f"Exact match on all columns. {after} rows remaining.",
                step=len(self.cleaning_log) + 1,
            )

            logger.info(f"✅ Duplicates removed: {removed}")

        except Exception as e:
            logger.error(f"❌ remove_duplicates error: {e}")
            self._add_log(
                log_type='warning',
                action="Duplicate removal failed",
                detail=str(e),
                step=len(self.cleaning_log) + 1,
            )


    # ==========================================
    # ✅ STEP 2: FILL MISSING VALUES
    # ==========================================
    def fill_missing_values(self):
        """
        Fill missing values based on column type.
        - Numeric  → mean / median
        - Text     → mode / 'Unknown'
        - DateTime → forward fill
        """
        try:
            total_filled = 0

            for col in self.df.columns:
                missing_count = self.df[col].isna().sum()

                if missing_count == 0:
                    continue

                col_dtype = self.df[col].dtype
                fill_value = None
                method_used = ""

                # ── Numeric columns ──
                if pd.api.types.is_numeric_dtype(col_dtype):
                    fill_method = Config.DEFAULT_NUMERIC_FILL

                    if fill_method == 'mean':
                        fill_value = round(self.df[col].mean(), 2)
                        method_used = f"Mean ({fill_value})"

                    elif fill_method == 'median':
                        fill_value = self.df[col].median()
                        method_used = f"Median ({fill_value})"

                    elif fill_method == 'mode':
                        mode_val = self.df[col].mode()
                        fill_value = mode_val[0] if len(mode_val) > 0 else 0
                        method_used = f"Mode ({fill_value})"

                    else:
                        fill_value = self.df[col].median()
                        method_used = f"Median ({fill_value})"

                    # Track change (first missing row)
                    first_missing = self.df[self.df[col].isna()].index
                    if len(first_missing) > 0:
                        self.changes.append({
                            'row': int(first_missing[0]) + 1,
                            'column': col,
                            'before': '(empty)',
                            'after': str(fill_value),
                            'action': f'{fill_method.title()} Fill',
                            'action_class': 'fill',
                        })

                    self.df[col] = self.df[col].fillna(fill_value)

                # ── DateTime columns ──
                elif pd.api.types.is_datetime64_any_dtype(col_dtype):
                    self.df[col] = self.df[col].fillna(method='ffill')
                    self.df[col] = self.df[col].fillna(method='bfill')
                    method_used = "Forward/Backward fill"

                # ── Text/Object columns ──
                else:
                    # Try mode first
                    mode_val = self.df[col].mode()
                    if len(mode_val) > 0 and mode_val[0] != '':
                        fill_value = mode_val[0]
                        method_used = f"Mode ({fill_value})"
                    else:
                        fill_value = Config.DEFAULT_TEXT_FILL
                        method_used = f"Default ('{fill_value}')"

                    # Track change
                    first_missing = self.df[self.df[col].isna()].index
                    if len(first_missing) > 0:
                        self.changes.append({
                            'row': int(first_missing[0]) + 1,
                            'column': col,
                            'before': '(empty)',
                            'after': str(fill_value),
                            'action': 'Auto-filled',
                            'action_class': 'fill',
                        })

                    self.df[col] = self.df[col].fillna(fill_value)
                    self.df[col] = self.df[col].replace('', fill_value)

                total_filled += int(missing_count)

                # Log per column
                self._add_log(
                    log_type='success',
                    action=f"Filled {missing_count} missing values in '{col}' column",
                    detail=f"Method: {method_used}",
                    step=len(self.cleaning_log) + 1,
                )

                logger.info(
                    f"📝 '{col}': filled {missing_count} missing → {method_used}"
                )

            self.stats['missing_filled'] = total_filled

            if total_filled == 0:
                self._add_log(
                    log_type='info',
                    action="No missing values found",
                    detail="All columns are complete",
                    step=len(self.cleaning_log) + 1,
                )

        except Exception as e:
            logger.error(f"❌ fill_missing_values error: {e}")
            self._add_log(
                log_type='warning',
                action="Missing value fill failed",
                detail=str(e),
                step=len(self.cleaning_log) + 1,
            )


    # ==========================================
    # ✅ STEP 3: FIX DATA TYPES
    # ==========================================
    def fix_data_types(self):
        """
        Fix incorrect data types.
        - Text numbers → int/float
        - Date strings → datetime
        - Boolean strings → bool
        - Currency strings → float
        """
        try:
            total_fixed = 0

            for col in self.df.columns:
                col_dtype = self.df[col].dtype

                # ── Try converting object → numeric ──
                if col_dtype == object:
                    fixed = self._try_convert_numeric(col)
                    if fixed > 0:
                        total_fixed += fixed
                        continue

                    # ── Try converting object → datetime ──
                    fixed = self._try_convert_datetime(col)
                    if fixed > 0:
                        total_fixed += fixed
                        continue

                    # ── Try converting object → bool ──
                    fixed = self._try_convert_boolean(col)
                    if fixed > 0:
                        total_fixed += fixed
                        continue

            self.stats['types_fixed'] = total_fixed

            if total_fixed > 0:
                self._add_log(
                    log_type='success',
                    action=f"Fixed {total_fixed} data type issues",
                    detail="Converted text to numbers, dates, booleans",
                    step=len(self.cleaning_log) + 1,
                )
            else:
                self._add_log(
                    log_type='info',
                    action="No data type issues found",
                    detail="All column types are correct",
                    step=len(self.cleaning_log) + 1,
                )

            logger.info(f"🔧 Types fixed: {total_fixed}")

        except Exception as e:
            logger.error(f"❌ fix_data_types error: {e}")
            self._add_log(
                log_type='warning',
                action="Data type fixing failed",
                detail=str(e),
                step=len(self.cleaning_log) + 1,
            )


    # ==========================================
    # ✅ STEP 4: STANDARDIZE TEXT
    # ==========================================
    def standardize_text(self):
        """
        Standardize all text/object columns.
        - Trim whitespace
        - Fix capitalization (title case)
        - Remove extra spaces
        - Remove special characters (optional)
        """
        try:
            total_standardized = 0

            for col in self.df.columns:
                if self.df[col].dtype != object:
                    continue

                col_standardized = 0
                original_values = self.df[col].copy()

                # Apply text cleaning
                self.df[col] = self.df[col].apply(
                    lambda x: self._clean_text_value(x)
                    if isinstance(x, str) else x
                )

                # Count changed values
                changed_mask = original_values != self.df[col]
                col_standardized = changed_mask.sum()

                if col_standardized > 0:
                    # Track first change
                    first_changed = original_values[changed_mask].index
                    if len(first_changed) > 0:
                        idx = first_changed[0]
                        self.changes.append({
                            'row': int(idx) + 1,
                            'column': col,
                            'before': str(original_values[idx]),
                            'after': str(self.df[col][idx]),
                            'action': 'Trimmed + Title Case',
                            'action_class': 'trim',
                        })

                    self._add_log(
                        log_type='success',
                        action=(
                            f"Standardized {col_standardized} "
                            f"text entries in '{col}' column"
                        ),
                        detail="Trimmed whitespace, applied title case",
                        step=len(self.cleaning_log) + 1,
                    )

                    logger.info(
                        f"✏️ '{col}': standardized {col_standardized} entries"
                    )

                total_standardized += col_standardized

            self.stats['text_standardized'] = total_standardized

            if total_standardized == 0:
                self._add_log(
                    log_type='info',
                    action="No text standardization needed",
                    detail="All text values are already clean",
                    step=len(self.cleaning_log) + 1,
                )

        except Exception as e:
            logger.error(f"❌ standardize_text error: {e}")
            self._add_log(
                log_type='warning',
                action="Text standardization failed",
                detail=str(e),
                step=len(self.cleaning_log) + 1,
            )


    # ==========================================
    # ✅ STEP 5: DETECT OUTLIERS
    # ==========================================
    def detect_outliers(self):
        """
        Detect outliers in numeric columns.
        Method: IQR or Z-score (from config)
        Flags outliers — does not remove by default.
        """
        try:
            total_outliers = 0
            method = Config.OUTLIER_METHOD

            for col in self.df.columns:
                if not pd.api.types.is_numeric_dtype(self.df[col].dtype):
                    continue

                col_series = self.df[col].dropna()

                if len(col_series) < 4:
                    continue

                outlier_mask = None

                # ── IQR Method ──
                if method == 'iqr':
                    Q1 = col_series.quantile(0.25)
                    Q3 = col_series.quantile(0.75)
                    IQR = Q3 - Q1

                    if IQR == 0:
                        continue

                    multiplier = Config.OUTLIER_IQR_MULTIPLIER
                    lower = Q1 - multiplier * IQR
                    upper = Q3 + multiplier * IQR

                    outlier_mask = (
                        (self.df[col] < lower) |
                        (self.df[col] > upper)
                    )

                # ── Z-Score Method ──
                elif method == 'zscore':
                    mean = col_series.mean()
                    std = col_series.std()

                    if std == 0:
                        continue

                    threshold = Config.OUTLIER_ZSCORE_THRESHOLD
                    z_scores = abs((self.df[col] - mean) / std)
                    outlier_mask = z_scores > threshold

                if outlier_mask is None:
                    continue

                col_outliers = int(outlier_mask.sum())

                if col_outliers > 0:
                    total_outliers += col_outliers

                    # Track first outlier
                    first_outlier_idx = self.df[outlier_mask].index
                    if len(first_outlier_idx) > 0:
                        idx = first_outlier_idx[0]
                        self.changes.append({
                            'row': int(idx) + 1,
                            'column': col,
                            'before': str(self.df[col][idx]),
                            'after': f"{self.df[col][idx]} ⚠️",
                            'action': 'Outlier Flagged',
                            'action_class': 'flag',
                        })

                    self._add_log(
                        log_type='warning',
                        action=(
                            f"{col_outliers} outliers detected "
                            f"in '{col}' column"
                        ),
                        detail=(
                            f"Method: {method.upper()} — "
                            f"Values flagged for review"
                        ),
                        step=len(self.cleaning_log) + 1,
                    )

                    logger.info(
                        f"📈 '{col}': {col_outliers} outliers ({method})"
                    )

            self.stats['outliers_found'] = total_outliers

            if total_outliers == 0:
                self._add_log(
                    log_type='info',
                    action="No outliers detected",
                    detail=f"Method used: {method.upper()}",
                    step=len(self.cleaning_log) + 1,
                )

        except Exception as e:
            logger.error(f"❌ detect_outliers error: {e}")
            self._add_log(
                log_type='warning',
                action="Outlier detection failed",
                detail=str(e),
                step=len(self.cleaning_log) + 1,
            )


    # ==========================================
    # ✅ CALCULATE QUALITY SCORE
    # ==========================================
    def calculate_quality_score(
        self,
        before_analysis: dict,
        after_analysis: dict
    ) -> float:
        """
        Calculate data quality score (0-100).
        Based on completeness, consistency,
        and issue resolution rate.
        """
        try:
            score = 100.0

            original_rows = len(self.original_df)
            if original_rows == 0:
                return 0.0

            # ── Deduct for duplicates ──
            dup_ratio = (
                self.stats['duplicates_removed'] / original_rows
            )
            score -= min(dup_ratio * 30, 15)

            # ── Deduct for missing values ──
            total_cells = (
                original_rows * len(self.original_df.columns)
            )
            if total_cells > 0:
                missing_ratio = (
                    self.stats['missing_filled'] / total_cells
                )
                score -= min(missing_ratio * 40, 20)

            # ── Deduct for type issues ──
            type_ratio = (
                self.stats['types_fixed'] / total_cells
                if total_cells > 0 else 0
            )
            score -= min(type_ratio * 20, 10)

            # ── Deduct for outliers ──
            outlier_ratio = (
                self.stats['outliers_found'] / original_rows
            )
            score -= min(outlier_ratio * 10, 5)

            # ── Bonus for completeness ──
            after_missing = after_analysis.get('total_missing', 0)
            if after_missing == 0:
                score = min(score + 5, 100)

            # ── Clamp to 0-100 ──
            score = max(0.0, min(100.0, score))

            logger.info(f"⭐ Quality score: {round(score, 1)}")
            return round(score, 1)

        except Exception as e:
            logger.error(f"❌ calculate_quality_score error: {e}")
            return 75.0


    # ==========================================
    # ✅ GET CLEANED DATA
    # ==========================================
    def get_cleaned_data(self) -> pd.DataFrame:
        """Return the cleaned DataFrame"""
        return self.df.copy()


    # ==========================================
    # ✅ GET CLEANING LOG
    # ==========================================
    def get_cleaning_log(self) -> list:
        """Return the cleaning log list"""
        return self.cleaning_log.copy()


    # ==========================================
    # ✅ GET CHANGES PREVIEW
    # ==========================================
    def get_changes_preview(self) -> list:
        """Return list of individual changes"""
        return self.changes[:200]  # Max 200 changes


    # ==========================================
    # ✅ PRIVATE: ADD LOG ENTRY
    # ==========================================
    def _add_log(
        self,
        log_type: str,
        action: str,
        detail: str,
        step: int,
    ):
        """Add entry to cleaning log"""
        self.cleaning_log.append({
            'type': log_type,
            'action': action,
            'detail': detail,
            'step': step,
            'timestamp': datetime.utcnow().isoformat(),
        })


    # ==========================================
    # ✅ PRIVATE: TRY CONVERT NUMERIC
    # ==========================================
    def _try_convert_numeric(self, col: str) -> int:
        """
        Try to convert object column to numeric.
        Handles currency, commas, percent signs.
        Returns count of fixed values.
        """
        try:
            sample = self.df[col].dropna().head(50)

            if len(sample) == 0:
                return 0

            # Check if column looks numeric
            def clean_numeric(val):
                if not isinstance(val, str):
                    return val
                # Remove currency, commas, spaces
                cleaned = re.sub(r'[$£€¥,\s%]', '', str(val).strip())
                return cleaned

            cleaned_sample = sample.apply(clean_numeric)

            try:
                pd.to_numeric(cleaned_sample, errors='raise')
            except (ValueError, TypeError):
                return 0

            # Apply to full column
            original = self.df[col].copy()
            self.df[col] = self.df[col].apply(
                lambda x: re.sub(r'[$£€¥,\s%]', '', str(x).strip())
                if isinstance(x, str) else x
            )
            self.df[col] = pd.to_numeric(self.df[col], errors='coerce')

            # Count how many changed
            changed = (original != self.df[col].astype(str)).sum()
            fixed = int(self.df[col].notna().sum())

            if fixed > 0:
                # Track change
                first_idx = original.index[0]
                self.changes.append({
                    'row': int(first_idx) + 1,
                    'column': col,
                    'before': str(original[first_idx]),
                    'after': str(self.df[col][first_idx]),
                    'action': 'Type Conversion',
                    'action_class': 'type',
                })

                self._add_log(
                    log_type='success',
                    action=(
                        f"Converted {fixed} values "
                        f"in '{col}' to numeric"
                    ),
                    detail="Removed currency symbols and commas",
                    step=len(self.cleaning_log) + 1,
                )

            return fixed

        except Exception:
            return 0


    # ==========================================
    # ✅ PRIVATE: TRY CONVERT DATETIME
    # ==========================================
    def _try_convert_datetime(self, col: str) -> int:
        """
        Try to convert object column to datetime.
        Returns count of fixed values.
        """
        try:
            # Check if column name hints at date
            date_keywords = [
                'date', 'time', 'day', 'month',
                'year', 'created', 'updated', 'joined',
            ]
            col_lower = col.lower()
            is_date_col = any(
                kw in col_lower for kw in date_keywords
            )

            if not is_date_col:
                return 0

            original = self.df[col].copy()

            # Try parsing
            converted = pd.to_datetime(
                self.df[col],
                infer_datetime_format=True,
                errors='coerce',
            )

            success_count = int(converted.notna().sum())
            original_count = int(original.notna().sum())

            # Only apply if mostly successful
            if success_count < original_count * 0.7:
                return 0

            # Format to standard format
            self.df[col] = converted.dt.strftime(
                Config.DEFAULT_DATE_FORMAT
            )

            fixed = int(
                (original.fillna('') != self.df[col].fillna('')).sum()
            )

            if fixed > 0:
                # Track change
                changed_idx = original[
                    original.fillna('') != self.df[col].fillna('')
                ].index

                if len(changed_idx) > 0:
                    idx = changed_idx[0]
                    self.changes.append({
                        'row': int(idx) + 1,
                        'column': col,
                        'before': str(original[idx]),
                        'after': str(self.df[col][idx]),
                        'action': 'Date Format',
                        'action_class': 'format',
                    })

                self._add_log(
                    log_type='success',
                    action=(
                        f"Fixed {fixed} date formats "
                        f"in '{col}' column"
                    ),
                    detail=(
                        f"Converted to "
                        f"{Config.DEFAULT_DATE_FORMAT} format"
                    ),
                    step=len(self.cleaning_log) + 1,
                )

                self.stats['format_fixed'] += fixed

            return fixed

        except Exception:
            return 0


    # ==========================================
    # ✅ PRIVATE: TRY CONVERT BOOLEAN
    # ==========================================
    def _try_convert_boolean(self, col: str) -> int:
        """
        Try to convert boolean string column.
        yes/no, true/false, 1/0 → bool
        Returns count of fixed values.
        """
        try:
            bool_maps = {
                'true': True,  'false': False,
                'yes': True,   'no': False,
                '1': True,     '0': False,
                'y': True,     'n': False,
                'on': True,    'off': False,
            }

            sample = self.df[col].dropna().head(30)

            if len(sample) == 0:
                return 0

            # Check if all values are boolean-like
            sample_lower = sample.apply(
                lambda x: str(x).strip().lower()
                if isinstance(x, str) else str(x)
            )

            all_bool = all(
                v in bool_maps for v in sample_lower
            )

            if not all_bool:
                return 0

            original = self.df[col].copy()

            # Apply conversion
            self.df[col] = self.df[col].apply(
                lambda x: bool_maps.get(
                    str(x).strip().lower(), x
                ) if pd.notna(x) else x
            )

            fixed = int((original != self.df[col]).sum())

            if fixed > 0:
                self._add_log(
                    log_type='success',
                    action=(
                        f"Converted {fixed} values "
                        f"in '{col}' to boolean"
                    ),
                    detail="yes/no, true/false → True/False",
                    step=len(self.cleaning_log) + 1,
                )

            return fixed

        except Exception:
            return 0


    # ==========================================
    # ✅ PRIVATE: CLEAN TEXT VALUE
    # ==========================================
    def _clean_text_value(self, value: str) -> str:
        """
        Clean a single text value.
        - Strip whitespace
        - Remove extra spaces
        - Title case
        - Remove leading/trailing special chars
        """
        if not isinstance(value, str):
            return value

        # Strip whitespace
        cleaned = value.strip()

        # Remove extra internal spaces
        cleaned = re.sub(r'\s+', ' ', cleaned)

        # Remove leading/trailing quotes
        cleaned = cleaned.strip('"\'')

        # Title case (only if all uppercase or all lowercase)
        if cleaned.isupper() or cleaned.islower():
            cleaned = cleaned.title()

        return cleaned