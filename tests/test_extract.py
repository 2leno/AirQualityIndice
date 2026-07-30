EXPECTED = [
    "european_aqi", "us_aqi", "pm2_5", "pm10",
    "nitrogen_dioxide", "ozone", "sulphur_dioxide", "carbon_monoxide",
]


class TestCurrentParameters:
    def test_expected_pollutants(self):
        assert EXPECTED == [
            "european_aqi", "us_aqi", "pm2_5", "pm10",
            "nitrogen_dioxide", "ozone", "sulphur_dioxide", "carbon_monoxide",
        ]

    def test_no_duplicates(self):
        assert len(EXPECTED) == len(set(EXPECTED))
