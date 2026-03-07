#!/usr/bin/env python3
"""
Future Forecast Prediction Script - Class-based API Module
Methodologically correct: no leakage, pure features.
"""

import pandas as pd
import numpy as np
from catboost import CatBoostRegressor
from datetime import datetime
import json

MODEL_FILE = "future_forecast_model.cbm"
FEATURE_INFO_FILE = "future_forecast_info.json"

SUBWAY_STATIONS = [
    "ΔΗΜΟΤΙΚΟ ΘΕΑΤΡΟ", "ΠΕΙΡΑΙΑΣ", "ΜΑΝΙΑΤΙΚΑ", "ΝΙΚΑΙΑ", "ΚΟΡΥΔΑΛΛΟΣ",
    "ΑΓΙΑ ΒΑΡΒΑΡΑ", "ΑΓΙΑ ΜΑΡΙΝΑ", "ΑΙΓΑΛΕΩ", "ΕΛΑΙΩΝΑΣ", "ΚΕΡΑΜΕΙΚΟΣ",
    "ΜΟΝΑΣΤΗΡΑΚΙ", "ΣΥΝΤΑΓΜΑ", "ΕΥΑΓΓΕΛΙΣΜOΣ", "ΜΕΓΑΡΟ ΜΟΥΣΙKΗΣ", "ΑΜΠΕΛΟΚΗΠΟΙ",
    "ΠΑΝOΡΜΟΥ", "ΚΑΤΕΧΑΚΗ", "ΕΘΝΙΚΗ ΑΜΥΝΑ", "ΧΟΛΑΡΓOΣ", "ΝΟΜΙΣΜΑTΟKΟΠΕΙΟ",
    "ΑΓΙΑ ΠΑΡΑΣKΕΥΗ", "ΧΑΛΑΝΔΡΙ", "ΔΟΥΚΙΣΣΗΣ ΠΛΑΚΕΝΤΙΑΣ", "ΠΑΛΛΗΝΗ",
    "ΠΑΙΑΝΙΑ - KΑΝTΖΑ", "ΚΟΡΩΠΙ", "ΑΕΡΟΔΡΟΜΙΟ"
]

class Predictor:
    def __init__(self):
        self.model = None
        self.FEATURES = []
        self.test_metrics = {}
        self.PRIORS = {}
        self.GLOBAL_PRIOR = {}
        self.MEDIANS = {}
        self.STATIONS_LIST = SUBWAY_STATIONS

    def init(self, model_path=MODEL_FILE, info_path=FEATURE_INFO_FILE):
        """Loads the model and the safe priors learned strictly during training."""
        try:
            self.model = CatBoostRegressor()
            self.model.load_model(model_path)

            with open(info_path, "r") as f:
                info = json.load(f)

            self.FEATURES = info["features"]
            self.test_metrics = info["test_metrics"]
            self.PRIORS = info.get("priors", {})
            self.GLOBAL_PRIOR = info.get("global_prior", {})
            self.MEDIANS = info.get("medians", {})

        except Exception as e:
            raise RuntimeError(f"Failed to load model or metadata: {e}")

    def _get_season(self, month):
        if month in [12, 1, 2]: return "winter"
        if month in [3, 4, 5]: return "spring"
        if month in [6, 7, 8]: return "summer"
        return "autumn"

    def _is_greek_holiday(self, ts: datetime):
        d, m, y = ts.day, ts.month, ts.year
        fixed = {(1, 1), (1, 6), (25, 3), (1, 5), (15, 8), (28, 10), (25, 12), (26, 12)}
        if (d, m) in fixed: return True
        if m == 8 and 8 <= d <= 15: return True
        easter = {
            2024: [(3, 5), (5, 5), (6, 5)],
            2025: [(18, 4), (20, 4), (21, 4)],
            2026: [(10, 4), (12, 4), (13, 4)],
        }
        return y in easter and (d, m) in easter[y]

    def _derive_day_of_week(self, ts):
        return (ts.isoweekday() % 7) + 1 

    def _derive_is_weekend(self, dow):
        return 1 if dow in (6, 7) else 0

    def _derive_is_peak(self, hour):
        return 1 if (7 <= hour <= 10) or (15 <= hour <= 18) else 0

    def predict(self, station_index, date_str, time_str, boarding_disembark, temperature, precipitation, cloud_cover, wind_speed):
        """
        Generates a forecast. Call init() once before using this.
        Expects raw weather features instead of an arbitrary score.
        """
        if self.model is None:
            raise RuntimeError("Model not loaded. Call init() first.")

        if not (0 <= station_index < len(self.STATIONS_LIST)):
            raise ValueError(f"Station index {station_index} out of bounds.")
        
        station_name = self.STATIONS_LIST[station_index]

        ts = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
        bd = boarding_disembark.strip().lower()
        is_boarding = 1 if bd == "b" else 0
        
        prior_key = f"{station_name}_{is_boarding}"
        pri = self.PRIORS.get(prior_key, self.GLOBAL_PRIOR)

        hour = ts.hour
        dow = self._derive_day_of_week(ts)
        month = ts.month

        row = {
            "dv_platenum_station": station_name,
            "is_boarding": str(is_boarding),
            "season": self._get_season(month),
            "is_weekend": str(self._derive_is_weekend(dow)),
            "is_holiday": str(1 if self._is_greek_holiday(ts) else 0),
            "is_peak_hour": str(self._derive_is_peak(hour)),
            "hour_of_day": hour,
            "day_of_week": dow,
            "month": month,
            "temperature_2m": float(temperature),
            "precipitation": float(precipitation),
            "cloud_cover": float(cloud_cover),
            "wind_speed_10m": float(wind_speed),
            "station_mean": pri["station_mean"],
            "station_total": pri["station_total"],
            "station_peak_ratio": pri["station_peak_ratio"],
        }

        # Handle missing numeric parameters gracefully if user passes None
        for col in ["temperature_2m", "precipitation", "cloud_cover", "wind_speed_10m"]:
            if row[col] is None or np.isnan(row[col]):
                row[col] = self.MEDIANS.get(col, 0.0)

        X = pd.DataFrame([row])[self.FEATURES]

        # Predict raw count directly (model trained with RMSE on original counts)
        pred = self.model.predict(X)[0]
        pred = max(0.0, float(pred))

        mae = self.test_metrics.get("mae", 50)
        lower, upper = max(0, pred - mae), pred + mae

        return (int(pred), int(lower), int(upper))
