"""
============================================
ANALYZER.PY — Data Analysis & Profiling
Analyze DataFrame before and after cleaning
============================================
"""

import logging
from datetime import datetime
from typing import Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


# ============================================
# ✅ DATA ANALYZER CLASS
# ============================================
class DataAnalyzer:
    """
    Analyze DataFrame structure, quality,
    and generate column profiles.
    Used before and after cleaning.
    """

    def __init__(self, df: pd.DataFrame):
        """
        Initialize analyzer with DataFrame.

        Args:
            df: pandas DataFrame to analyze
        """
        self.df = df.copy()
        self.rows, self.cols = df.shape
        self._analysis_cache = None

        logger.info(
            f"🔍 DataAnalyzer initialized: "
            f"{self.rows} rows × {self.cols} cols"
        )


    # ==========================================
    # ✅ MAIN ANALYZE METHOD
    # ==========================================
    def analyze(self) -> dict:
        """
        Run full analysis on DataFrame.
        Returns comprehensive analysis dict.
        """
        try:
            logger.info("🔍 Running full data analysis...")

            analysis = {
                'shape': {
                    'rows': self.rows,
                    'cols': self.cols,
                    'total_cells': self.rows * self.cols,
                },
                'total_missing': self._count_total_missing(),
                'total_duplicates': self._count_duplicates(),
                'missing_per_column': self._missing_per_column(),
                'dtype_summary': self._dtype_summary(),
                'column_issues': self._column_issues(),
                'completeness_score': self._completeness_score(),
                'analyzed_at': datetime.utcnow().isoformat(),
            }

            # Cache result
            self._analysis_cache = analysis

            logger.info(
                f"✅ Analysis complete — "
                f"Missing: {analysis['total_missing']}, "
                f"Duplicates: {analysis['total_duplicates']}"
            )

            return analysis

        except Exception as e:
            logger.error(f"❌ analyze error: {e}")
            return {
                'shape': {'rows': self.rows, 'cols': self.cols},
                'total_missing': 0,
                'total_duplicates': 0,
                'error': str(e),
            }


    # ==========================================
    # ✅ COUNT TOTAL MISSING VALUES
    # ==========================================
    def _count_total_missing(self) -> int:
        """Count total missing values in DataFrame"""
        try:
            total = int(self.df.isna().sum().sum())
            # Also count empty strings
            empty_strings = int(
                (self.df == '').sum().sum()
            )
            return total + empty_strings
        except Exception:
            return 0


    # ==========================================
    # ✅ COUNT DUPLICATE ROWS
    # ==========================================
    def _count_duplicates(self) -> int:
        """Count duplicate rows in DataFrame"""
        try:
            return int(self.df.duplicated().sum())
        except Exception:
            return 0


    # ==========================================
    # ✅ MISSING PER COLUMN
    # ==========================================
    def _missing_per_column(self) -> dict:
        """
        Get missing value count per column.
        Returns { col_name: missing_count }
        """
        try:
            missing = {}
            for col in self.df.columns:
                null_count = int(self.df[col].isna().sum())
                empty_count = int(
                    (self.df[col] == '').sum()
                ) if self.df[col].dtype == object else 0
                missing[col] = null_count + empty_count
            return missing
        except Exception:
            return {}


    # ==========================================
    # ✅ DTYPE SUMMARY
    # ==========================================
    def _dtype_summary(self) -> dict:
        """
        Summarize column data types.
        Returns { col_name: type_label }
        """
        try:
            summary = {}
            for col in self.df.columns:
                dtype = self.df[col].dtype

                if pd.api.types.is_integer_dtype(dtype):
                    label = 'Integer'
                elif pd.api.types.is_float_dtype(dtype):
                    label = 'Float'
                elif pd.api.types.is_bool_dtype(dtype):
                    label = 'Boolean'
                elif pd.api.types.is_datetime64_any_dtype(dtype):
                    label = 'DateTime'
                elif dtype == object:
                    # Check if it looks like dates
                    label = self._detect_object_subtype(col)
                else:
                    label = str(dtype)

                summary[col] = label

            return summary

        except Exception:
            return {}


    # ==========================================
    # ✅ DETECT OBJECT SUBTYPE
    # ==========================================
    def _detect_object_subtype(self, col: str) -> str:
        """
        Detect what kind of data an object column holds.
        Returns: 'Text', 'Date', 'Numeric', 'Mixed'
        """
        try:
            sample = self.df[col].dropna().head(20)

            if len(sample) == 0:
                return 'Text'

            # Check for date keywords in column name
            date_keywords = [
                'date', 'time', 'day', 'month',
                'year', 'created', 'updated', 'joined',
            ]
            if any(kw in col.lower() for kw in date_keywords):
                return 'Date'

            # Try numeric
            try:
                pd.to_numeric(sample, errors='raise')
                return 'Numeric'
            except (ValueError, TypeError):
                pass

            # Try datetime
            try:
                pd.to_datetime(sample.head(5), errors='raise')
                return 'Date'
            except (ValueError, TypeError):
                pass

            return 'Text'

        except Exception:
            return 'Text'


    # ==========================================
    # ✅ COLUMN ISSUES
    # ==========================================
    def _column_issues(self) -> dict:
        """
        Count total issues per column.
        Returns { col_name: issue_count }
        Used for horizontal bar chart.
        """
        try:
            issues = {}
            missing_per_col = self._missing_per_column()

            for col in self.df.columns:
                col_issues = 0

                # Missing values
                col_issues += missing_per_col.get(col, 0)

                # Whitespace issues (text columns)
                if self.df[col].dtype == object:
                    whitespace_issues = int(
                        self.df[col].dropna().apply(
                            lambda x: isinstance(x, str) and (
                                x != x.strip() or
                                '  ' in x
                            )
                        ).sum()
                    )
                    col_issues += whitespace_issues

                    # Case issues
                    case_issues = int(
                        self.df[col].dropna().apply(
                            lambda x: isinstance(x, str) and (
                                x.isupper() or x.islower()
                            ) and len(x) > 2
                        ).sum()
                    )
                    col_issues += case_issues

                issues[col] = col_issues

            return issues

        except Exception:
            return {}


    # ==========================================
    # ✅ COMPLETENESS SCORE
    # ==========================================
    def _completeness_score(self) -> float:
        """
        Calculate data completeness percentage.
        (non-missing / total cells) × 100
        """
        try:
            total_cells = self.rows * self.cols
            if total_cells == 0:
                return 100.0

            missing = self._count_total_missing()
            score = ((total_cells - missing) / total_cells) * 100
            return round(score, 1)

        except Exception:
            return 100.0


    # ==========================================
    # ✅ GET COLUMN PROFILES
    # ==========================================
    def get_column_profiles(self) -> list:
        """
        Generate detailed profile for each column.
        Used for dashboard column profile cards.
        """
        try:
            profiles = []
            dtype_summary = self._dtype_summary()
            missing_per_col = self._missing_per_column()

            for col in self.df.columns:
                try:
                    profile = self._profile_single_column(
                        col,
                        dtype_summary.get(col, 'Text'),
                        missing_per_col.get(col, 0),
                    )
                    profiles.append(profile)

                except Exception as e:
                    logger.warning(f"⚠️ Profile failed for '{col}': {e}")
                    profiles.append({
                        'name': col,
                        'type': 'Unknown',
                        'type_class': 'text-type',
                        'total': self.rows,
                        'missing_before': 0,
                        'issues_fixed': 0,
                        'extra_label': 'Info',
                        'extra_value': 'N/A',
                        'completeness': 0,
                        'icon': 'fa-question',
                    })

            logger.info(
                f"✅ Column profiles generated: {len(profiles)} columns"
            )

            return profiles

        except Exception as e:
            logger.error(f"❌ get_column_profiles error: {e}")
            return []


    # ==========================================
    # ✅ PROFILE SINGLE COLUMN
    # ==========================================
    def _profile_single_column(
        self,
        col: str,
        col_type: str,
        missing_count: int,
    ) -> dict:
        """
        Generate profile for a single column.
        Returns profile dict for frontend card.
        """
        col_data = self.df[col]
        total = len(col_data)
        non_null = int(col_data.notna().sum())
        completeness = round((non_null / total) * 100, 1) if total > 0 else 0

        # Type class and icon
        type_map = {
            'Integer': ('num-type',  'fa-hashtag'),
            'Float':   ('num-type',  'fa-hashtag'),
            'Numeric': ('num-type',  'fa-hashtag'),
            'Text':    ('text-type', 'fa-font'),
            'Date':    ('date-type', 'fa-calendar'),
            'DateTime':('date-type', 'fa-calendar'),
            'Boolean': ('bool-type', 'fa-toggle-on'),
            'Unknown': ('text-type', 'fa-question'),
        }

        type_class, icon = type_map.get(
            col_type, ('text-type', 'fa-font')
        )

        # Extra stats based on type
        extra_label = 'Unique Values'
        extra_value = str(int(col_data.nunique()))

        if col_type in ('Integer', 'Float', 'Numeric'):
            numeric_col = pd.to_numeric(col_data, errors='coerce')
            mean_val = round(float(numeric_col.mean()), 2) if non_null > 0 else 0
            median_val = round(float(numeric_col.median()), 2) if non_null > 0 else 0
            min_val = round(float(numeric_col.min()), 2) if non_null > 0 else 0
            max_val = round(float(numeric_col.max()), 2) if non_null > 0 else 0

            extra_label = 'Mean / Median'
            extra_value = f"{mean_val} / {median_val}"

        elif col_type in ('Date', 'DateTime'):
            extra_label = 'Date Range'
            try:
                date_col = pd.to_datetime(col_data, errors='coerce')
                min_date = date_col.min()
                max_date = date_col.max()

                if pd.notna(min_date) and pd.notna(max_date):
                    extra_value = (
                        f"{min_date.strftime('%Y-%m')} — "
                        f"{max_date.strftime('%Y-%m')}"
                    )
                else:
                    extra_value = 'N/A'
            except Exception:
                extra_value = 'N/A'

        elif col_type == 'Boolean':
            try:
                val_counts = col_data.value_counts()
                true_count = int(val_counts.get(True, 0))
                false_count = int(val_counts.get(False, 0))
                extra_label = 'True / False'
                extra_value = f"{true_count} / {false_count}"
            except Exception:
                extra_value = 'N/A'

        return {
            'name': col,
            'icon': icon,
            'type': col_type,
            'type_class': type_class,
            'total': total,
            'missing_before': missing_count,
            'issues_fixed': missing_count,
            'extra_label': extra_label,
            'extra_value': extra_value,
            'completeness': completeness,
        }


    # ==========================================
    # ✅ GET BEFORE AFTER COMPARISON
    # ==========================================
    def get_before_after_data(
        self,
        after_analyzer: 'DataAnalyzer'
    ) -> dict:
        """
        Compare before and after analysis.
        Returns data for before/after bar chart.
        """
        try:
            before_missing = self._missing_per_column()
            after_missing = after_analyzer._missing_per_column()

            labels = list(self.df.columns)
            before_values = [
                before_missing.get(col, 0) for col in labels
            ]
            after_values = [
                after_missing.get(col, 0) for col in labels
            ]

            return {
                'labels': labels,
                'before': before_values,
                'after': after_values,
            }

        except Exception as e:
            logger.error(f"❌ get_before_after_data error: {e}")
            return {
                'labels': [],
                'before': [],
                'after': [],
            }


    # ==========================================
    # ✅ GET SUMMARY STATS
    # ==========================================
    def get_summary_stats(self) -> dict:
        """
        Get quick summary statistics.
        Used for dashboard stat cards.
        """
        try:
            return {
                'total_rows': self.rows,
                'total_cols': self.cols,
                'total_missing': self._count_total_missing(),
                'total_duplicates': self._count_duplicates(),
                'completeness': self._completeness_score(),
                'numeric_cols': int(
                    self.df.select_dtypes(
                        include=[np.number]
                    ).shape[1]
                ),
                'text_cols': int(
                    self.df.select_dtypes(
                        include=['object']
                    ).shape[1]
                ),
                'datetime_cols': int(
                    self.df.select_dtypes(
                        include=['datetime64']
                    ).shape[1]
                ),
            }

        except Exception as e:
            logger.error(f"❌ get_summary_stats error: {e}")
            return {
                'total_rows': self.rows,
                'total_cols': self.cols,
                'total_missing': 0,
                'total_duplicates': 0,
                'completeness': 0,
            }


    # ==========================================
    # ✅ GET COLUMN ISSUES FOR CHART
    # ==========================================
    def get_column_issues_chart_data(self) -> dict:
        """
        Get column issues data formatted
        for horizontal bar chart.
        """
        try:
            issues = self._column_issues()

            # Sort by issue count descending
            sorted_issues = sorted(
                issues.items(),
                key=lambda x: x[1],
                reverse=True,
            )

            labels = [item[0] for item in sorted_issues]
            values = [item[1] for item in sorted_issues]

            return {
                'labels': labels,
                'issues': values,
            }

        except Exception as e:
            logger.error(
                f"❌ get_column_issues_chart_data error: {e}"
            )
            return {'labels': [], 'issues': []}