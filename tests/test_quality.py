import pytest
import pandas as pd
from src.quality import (
    missing_values_report,
    duplicates_report,
    range_check,
    dtypes_check,
    quality_report_stage,
    PHYSICAL_RANGES,
)


class TestMissingValues:
    def test_no_missing(self, sample_raw):
        result = missing_values_report(sample_raw)
        assert all(v == 0 for v in result.values())

    def test_with_nulls(self, sample_raw_with_nulls):
        result = missing_values_report(sample_raw_with_nulls)
        assert result["pm2_5"] == 1
        assert result["ozone"] == 1
        assert result["city_name"] == 0


class TestDuplicates:
    def test_no_duplicates(self, sample_raw):
        assert duplicates_report(sample_raw) == 0

    def test_with_duplicates(self, sample_raw):
        df = pd.concat([sample_raw, sample_raw.iloc[[0]]], ignore_index=True)
        assert duplicates_report(df) == 1

    def test_subset_duplicates(self, sample_raw):
        df = pd.concat([sample_raw, sample_raw], ignore_index=True)
        assert duplicates_report(df, subset=["city_name", "timestamp"]) == 5


class TestRangeCheck:
    def test_all_in_range(self, sample_raw):
        violations = range_check(sample_raw, PHYSICAL_RANGES)
        assert violations == {}

    def test_out_of_range(self):
        df = pd.DataFrame({"pm2_5": [2500.0, -1.0, 10.0]})
        violations = range_check(df, {"pm2_5": (0.0, 2000.0)})
        assert violations["pm2_5"] == 2

    def test_ignore_missing_column(self):
        df = pd.DataFrame({"foo": [1.0]})
        assert range_check(df, PHYSICAL_RANGES) == {}


class TestDtypesCheck:
    def test_match(self):
        df = pd.DataFrame({"a": [1, 2], "b": [1.0, 2.0]})
        expected = {"a": "int64", "b": "float64"}
        assert dtypes_check(df, expected) == []

    def test_mismatch(self):
        df = pd.DataFrame({"a": [1.0, 2.0]})
        expected = {"a": "int64"}
        mismatches = dtypes_check(df, expected)
        assert len(mismatches) == 1
        assert "a" in mismatches[0]

    def test_missing_column(self):
        df = pd.DataFrame({"a": [1]})
        mismatches = dtypes_check(df, {"b": "int64"})
        assert len(mismatches) == 1
        assert "manquante" in mismatches[0]


class TestQualityReport:
    def test_returns_dict(self, sample_raw):
        report = quality_report_stage("test", sample_raw)
        assert report["stage"] == "test"
        assert report["rows"] == 5
        assert "missing_values" in report
        assert "duplicates" in report

    def test_with_ranges(self, sample_raw):
        report = quality_report_stage("test", sample_raw, ranges=PHYSICAL_RANGES)
        assert "range_violations" in report
        assert report["range_violations"] == {}

    def test_with_dtypes(self, sample_raw):
        expected = {"city_name": "str", "pm2_5": "float64"}
        report = quality_report_stage("test", sample_raw, expected_dtypes=expected)
        mismatches = report.get("dtype_mismatches", [])
        assert all("pm2_5" not in m for m in mismatches)
