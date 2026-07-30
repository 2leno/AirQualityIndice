import pytest
import pandas as pd
from src.transform import (
    _build_dim_pollutant,
    _build_dim_date,
    _compute_exceeds_threshold,
    POLLUTANT_META,
)


class TestDimPollutant:
    def test_returns_correct_columns(self, sample_dim_pollutant_category):
        df = _build_dim_pollutant(sample_dim_pollutant_category)
        expected_cols = [
            "pollutant_id", "pollutant_code", "pollutant_name",
            "unit", "who_threshold", "category_id",
        ]
        assert list(df.columns) == expected_cols

    def test_all_pollutants_present(self, sample_dim_pollutant_category):
        df = _build_dim_pollutant(sample_dim_pollutant_category)
        assert len(df) == len(POLLUTANT_META)
        assert set(df["pollutant_code"]) == set(POLLUTANT_META.keys())

    def test_category_mapping(self, sample_dim_pollutant_category):
        df = _build_dim_pollutant(sample_dim_pollutant_category)
        aqi = df[df["pollutant_code"].isin(["european_aqi", "us_aqi"])]
        assert (aqi["category_id"] == 1).all()

        particules = df[df["pollutant_code"].isin(["pm2_5", "pm10"])]
        assert (particules["category_id"] == 2).all()

        gaz = df[~df["pollutant_code"].isin(["european_aqi", "us_aqi", "pm2_5", "pm10"])]
        assert (gaz["category_id"] == 3).all()


class TestDimDate:
    def test_returns_correct_columns(self):
        timestamps = pd.Index(["2026-07-30T12:00:00", "2026-07-31T00:00:00"])
        df = _build_dim_date(timestamps)
        expected_cols = [
            "full_datetime", "date_id", "hour", "day",
            "month", "year", "quarter", "day_of_week",
        ]
        assert list(df.columns) == expected_cols

    def test_date_id_is_deterministic(self):
        ts = pd.Index(["2026-07-30T12:00:00"])
        df1 = _build_dim_date(ts)
        df2 = _build_dim_date(ts)
        assert df1["date_id"].iloc[0] == df2["date_id"].iloc[0]

    def test_date_parts_are_correct(self):
        timestamps = pd.Index(["2026-07-30T14:30:00"])
        df = _build_dim_date(timestamps)
        row = df.iloc[0]
        assert row["hour"] == 14
        assert row["day"] == 30
        assert row["month"] == 7
        assert row["year"] == 2026
        assert row["quarter"] == 3
        assert row["day_of_week"] == 3  # Thursday


class TestExceedsThreshold:
    def test_below_threshold(self, sample_fact, sample_dim_pollutant_category):
        dim_poll = _build_dim_pollutant(sample_dim_pollutant_category)
        fact = sample_fact.copy()
        fact["value"] = 1.0  # well below all thresholds
        result = _compute_exceeds_threshold(fact, dim_poll)
        assert result.sum() == 0

    def test_above_threshold(self, sample_fact, sample_dim_pollutant_category):
        dim_poll = _build_dim_pollutant(sample_dim_pollutant_category)
        fact = sample_fact.copy()
        fact["value"] = 99999.0  # above all thresholds
        result = _compute_exceeds_threshold(fact, dim_poll)
        # AQI pollutants have threshold=None, skip them
        aqi_ids = dim_poll[dim_poll["pollutant_code"].isin(["european_aqi", "us_aqi"])]["pollutant_id"].tolist()
        aqi_rows = fact[fact["pollutant_id"].isin(aqi_ids)]
        non_aqi_rows = fact[~fact["pollutant_id"].isin(aqi_ids)]
        assert result.sum() == len(non_aqi_rows)
