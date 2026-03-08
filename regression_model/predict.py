#!/usr/bin/env python3

import json
from datetime import date, datetime, timedelta

import numpy as np
import pandas as pd
from catboost import CatBoostRegressor

MODEL_FILE        = "future_forecast_model.cbm"
FEATURE_INFO_FILE = "future_forecast_info.json"

SUBWAY_STATIONS = [
    "ΔΗΜΟΤΙΚΟ ΘΕΑΤΡΟ", "ΠΕΙΡΑΙΑΣ", "ΜΑΝΙΑΤΙΚΑ", "ΝΙΚΑΙΑ", "ΚΟΡΥΔΑΛΛΟΣ",
    "ΑΓΙΑ ΒΑΡΒΑΡΑ", "ΑΓΙΑ ΜΑΡΙΝΑ", "ΑΙΓΑΛΕΩ", "ΕΛΑΙΩΝΑΣ", "ΚΕΡΑΜΕΙΚΟΣ",
    "ΜΟΝΑΣΤΗΡΑΚΙ", "ΣΥΝΤΑΓΜΑ", "ΕΥΑΓΓΕΛΙΣΜOΣ", "ΜΕΓΑΡΟ ΜΟΥΣΙKΗΣ", "ΑΜΠΕΛΟΚΗΠΟΙ",
    "ΠΑΝOΡΜΟΥ", "ΚΑΤΕΧΑΚΗ", "ΕΘΝΙΚΗ ΑΜΥΝΑ", "ΧΟΛΑΡΓOΣ", "ΝΟΜΙΣΜΑTΟKΟΠΕΙΟ",
    "ΑΓΙΑ ΠΑΡΑΣKΕΥΗ", "ΧΑΛΑΝΔΡΙ", "ΔΟΥΚΙΣΣΗΣ ΠΛΑΚΕΝΤΙΑΣ", "ΠΑΛΛΗΝΗ",
    "ΠΑΙΑΝΙΑ - KΑΝTΖΑ", "ΚΟΡΩΠΙ", "ΑΕΡΟΔΡΟΜΙΟ",
]

_ORTHODOX_EASTER = {
    2020: date(2020, 4, 19), 2021: date(2021, 5, 2),  2022: date(2022, 4, 24),
    2023: date(2023, 4, 16), 2024: date(2024, 5, 5),  2025: date(2025, 4, 20),
    2026: date(2026, 4, 12),
}

_SEASON_MAP = {
    12: "winter",  1: "winter",  2: "winter",
     3: "spring",  4: "spring",  5: "spring",
     6: "summer",  7: "summer",  8: "summer",
     9: "autumn", 10: "autumn", 11: "autumn",
}

# Must stay in sync with add_features.py and train_model.py
_HOUR_BUCKET_BINS   = [0, 6, 10, 15, 19, 24]
_HOUR_BUCKET_LABELS = ["night", "am_peak", "midday", "pm_peak", "evening"]

_RAIN_BINS   = [-1, 0, 1, 5, 100]
_RAIN_LABELS = ["none", "light", "moderate", "heavy"]

_TEMP_BINS   = [-20, 5, 15, 25, 35, 50]
_TEMP_LABELS = ["cold", "cool", "mild", "warm", "hot"]


def _build_greek_holidays(start_year: int = 2020, end_year: int = 2026) -> dict:
    holidays: dict = {}
    for year in range(start_year, end_year + 1):
        easter = _ORTHODOX_EASTER.get(year)
        if not easter:
            continue
        holidays[date(year, 1,  1)]  = "other"
        holidays[date(year, 1,  6)]  = "other"
        holidays[date(year, 3, 25)]  = "national_day"
        holidays[date(year, 5,  1)]  = "other"
        holidays[date(year, 8, 15)]  = "other"
        holidays[date(year, 10, 28)] = "national_day"
        holidays[date(year, 12, 25)] = "christmas"
        holidays[date(year, 12, 26)] = "christmas"
        holidays[easter - timedelta(days=48)] = "easter"
        holidays[easter - timedelta(days=2)]  = "easter"
        holidays[easter]                       = "easter"
        holidays[easter + timedelta(days=1)]  = "easter"
        holidays[easter + timedelta(days=50)] = "easter"
        for d in range(8, 16):
            holidays[date(year, 8, d)] = "summer_closure"
    return holidays


_GREEK_HOLIDAYS: dict = _build_greek_holidays()


def _bin(value: float, bins: list, labels: list) -> str:
    for i in range(len(bins) - 1):
        if bins[i] <= value < bins[i + 1]:
            return labels[i]
    return labels[-1]


def _hour_bucket(hour: int) -> str:
    return _bin(hour, _HOUR_BUCKET_BINS, _HOUR_BUCKET_LABELS)


def _rain_intensity(precipitation: float) -> str:
    return _bin(precipitation, _RAIN_BINS, _RAIN_LABELS)


def _temp_band(temperature: float) -> str:
    return _bin(temperature, _TEMP_BINS, _TEMP_LABELS)


class Predictor:
    def __init__(self):
        self.model: CatBoostRegressor | None = None
        self.FEATURES: list     = []
        self.test_metrics: dict = {}
        self.PRIORS: dict       = {}
        self.GLOBAL_PRIOR: dict = {}
        self.MEDIANS: dict      = {}
        self.STATIONS_LIST: list = SUBWAY_STATIONS

    def init(self, model_path: str = MODEL_FILE, info_path: str = FEATURE_INFO_FILE) -> None:
        """Load model and training-derived metadata. Must be called before predict()."""
        self.model = CatBoostRegressor()
        self.model.load_model(model_path)
        with open(info_path, "r") as f:
            info = json.load(f)
        self.FEATURES     = info["features"]
        self.test_metrics = info["test_metrics"]
        self.PRIORS       = info.get("priors", {})
        self.GLOBAL_PRIOR = info.get("global_prior", {})
        self.MEDIANS      = info.get("medians", {})

    # Internal helpers

    @staticmethod
    def _season(month: int) -> str:
        return _SEASON_MAP[month]

    @staticmethod
    def _holiday_type(d: date) -> str:
        return _GREEK_HOLIDAYS.get(d, "none")

    @staticmethod
    def _day_of_week(ts: datetime) -> int:
        return ts.isoweekday()

    @staticmethod
    def _is_weekend(dow: int) -> int:
        return 1 if dow >= 6 else 0

    @staticmethod
    def _is_peak_hour(hour: int) -> int:
        return 1 if (7 <= hour <= 10) or (15 <= hour <= 18) else 0

    def _safe(self, value, col: str) -> float:
        if value is None or (isinstance(value, float) and np.isnan(value)):
            return float(self.MEDIANS.get(col, 0.0))
        return float(value)

    # Public API

    def predict(
        self,
        station_index: int,
        date_str: str,
        time_str: str,
        boarding_disembark: str,
        temperature: float,
        precipitation: float,
        cloud_cover: float,
        wind_speed: float,
        routes_per_hour: float | None = None,
    ) -> tuple[int, int, int]:
        """
        Return (predicted_count, lower_bound, upper_bound).

        Parameters
        ----------
        station_index       : 0-based index into SUBWAY_STATIONS
        date_str            : "YYYY-MM-DD"
        time_str            : "HH:MM"
        boarding_disembark  : "b" for boarding, "d" for disembarking
        temperature         : degrees Celsius
        precipitation       : mm
        cloud_cover         : percent (0-100)
        wind_speed          : km/h
        routes_per_hour     : scheduled trains per hour (optional; uses training median if None)
        """
        if self.model is None:
            raise RuntimeError("Model not loaded. Call init() first.")
        if not (0 <= station_index < len(self.STATIONS_LIST)):
            raise ValueError(
                f"Station index {station_index} out of range (0-{len(self.STATIONS_LIST)-1})."
            )

        station    = self.STATIONS_LIST[station_index]
        ts         = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
        is_boarding = 1 if boarding_disembark.strip().lower() == "b" else 0

        hour  = ts.hour
        dow   = self._day_of_week(ts)
        month = ts.month
        hb    = _hour_bucket(hour)

        # Stratified prior: station + direction + hour bucket
        prior_key = f"{station}_{is_boarding}_{hb}"
        pri       = self.PRIORS.get(prior_key, self.GLOBAL_PRIOR)

        temp   = self._safe(temperature,   "temperature_2m")
        precip = self._safe(precipitation, "precipitation")

        row = {
            # Categorical
            "dv_platenum_station": station,
            "is_boarding":         str(is_boarding),
            "season":              self._season(month),
            "is_weekend":          str(self._is_weekend(dow)),
            "is_holiday":          str(int(self._holiday_type(ts.date()) != "none")),
            "is_peak_hour":        str(self._is_peak_hour(hour)),
            "hour_bucket":         hb,
            "holiday_type":        self._holiday_type(ts.date()),
            "station_dow":         f"{station}_{dow}",
            "station_hour":        f"{station}_{hour}",
            "station_month":       f"{station}_{month}",
            "rain_intensity":      _rain_intensity(precip),
            "temp_band":           _temp_band(temp),
            # Numeric
            "hour_of_day":         hour,
            "day_of_week":         dow,
            "month":               month,
            "temperature_2m":      temp,
            "precipitation":       precip,
            "cloud_cover":         self._safe(cloud_cover, "cloud_cover"),
            "wind_speed_10m":      self._safe(wind_speed,  "wind_speed_10m"),
            "routes_per_hour":     self._safe(routes_per_hour, "routes_per_hour"),
            "station_mean":        pri["station_mean"],
            "station_total":       pri["station_total"],
            "station_peak_ratio":  pri["station_peak_ratio"],
        }

        X    = pd.DataFrame([row])[self.FEATURES]
        pred = float(max(0.0, self.model.predict(X)[0]))
        mae  = self.test_metrics.get("mae", 50)

        return (int(pred), int(max(0, pred - mae)), int(pred + mae))