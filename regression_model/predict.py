#!/usr/bin/env python3
"""
Future Forecast Prediction Script (V5 Compatible) - Class-based API Module

- `Predictor` class to hold state and logic.
- `predictor.init()`: Loads model and priors into the instance.
- `predictor.predict()`: Takes a station index and returns (pred, low, high).
"""

import pandas as pd
import numpy as np
from catboost import CatBoostRegressor
from datetime import datetime
import json

# Constants 
MODEL_FILE = "future_forecast_model.cbm"
FEATURE_INFO_FILE = "future_forecast_info.json"
TRAIN_DATA = "subway_forecast_ready.csv"

# Master list of stations, referenced by index
SUBWAY_STATIONS = [
    "ΔΗΜΟΤΙΚΟ ΘΕΑΤΡΟ", "ΠΕΙΡΑΙΑΣ", "ΜΑΝΙΑΤΙΚΑ", "ΝΙΚΑΙΑ", "ΚΟΡΥΔΑΛΛΟΣ",
    "ΑΓΙΑ ΒΑΡΒΑΡΑ", "ΑΓΙΑ ΜΑΡΙΝΑ", "ΑΙΓΑΛΕΩ", "ΕΛΑΙΩΝΑΣ", "ΚΕΡΑΜΕΙΚΟΣ",
    "ΜΟΝΑΣΤΗΡΑΚΙ", "ΣΥΝΤΑΓΜΑ", "ΕΥΑΓΓΕΛΙΣΜOΣ", "ΜΕΓΑΡΟ ΜΟΥΣΙKΗΣ", "ΑΜΠΕΛΟΚΗΠΟΙ",
    "ΠΑΝOΡΜΟΥ", "ΚΑΤΕΧΑΚΗ", "ΕΘΝΙΚΗ ΑΜΥΝΑ", "ΧΟΛΑΡΓOΣ", "ΝΟΜΙΣΜΑTΟKΟΠΕΙΟ",
    "ΑΓΙΑ ΠΑΡΑΣKΕΥΗ", "ΧΑΛΑΝΔΡΙ", "ΔΟΥΚΙΣΣΗΣ ΠΛΑΚΕΝΤΙΑΣ", "ΠΑΛΛΗΝΗ",
    "ΠΑΙΑΝΙΑ - KΑΝTΖΑ", "ΚΟΡΩΠΙ", "ΑΕΡΟΔΡΟΜΙΟ"
]

class Predictor:
    """
    Wraps the subway forecast model for API usage.
    """
    def __init__(self):
        self.model = None
        self.FEATURES = []
        self.train_on_log = True
        self.test_metrics = {}
        self.PRIORS = {}
        self.GLOBAL_PRIOR = {}
        self.STATIONS_LIST = SUBWAY_STATIONS

    def init(self, model_path=MODEL_FILE, info_path=FEATURE_INFO_FILE, data_path=TRAIN_DATA):
        """
        Loads the model, metadata, and station priors into the instance.
        This function should be called once on application startup.
        """
        # 1. Load Model and Metadata
        try:
            self.model = CatBoostRegressor()
            self.model.load_model(model_path)

            with open(info_path, "r") as f:
                info = json.load(f)

            self.FEATURES = info["features"]
            self.test_metrics = info["test_metrics"]
            self.train_on_log = info.get("train_on_log_scale", True)

        except Exception as e:
            raise RuntimeError(f"Failed to load model or metadata: {e}")

        # 2. Load Training Data and Build Priors
        try:
            df = pd.read_csv(data_path, low_memory=False)

            station_stats = df.groupby("dv_platenum_station")["dv_validations"].agg(
                station_mean="mean",
                station_max="max",
                station_total="sum"
            ).reset_index()

            station_stats["station_peak_ratio"] = (
                station_stats["station_max"] / (station_stats["station_mean"] + 1e-9)
            )

            self.PRIORS = {
                row["dv_platenum_station"]: {
                    "station_mean": float(row["station_mean"]),
                    "station_total": float(row["station_total"]),
                    "station_peak_ratio": float(row["station_peak_ratio"])
                }
                for _, row in station_stats.iterrows()
            }

            self.GLOBAL_PRIOR = {
                "station_mean": df["dv_validations"].mean(),
                "station_total": df["dv_validations"].sum() / df["dv_platenum_station"].nunique(),
                "station_peak_ratio": 2.0  # safe neutral fallback
            }

        except Exception as e:
            raise RuntimeError(f"Failed to load and process station priors: {e}")

    # 
    # Private Helpers
    # 

    def _get_season(self, month):
        if month in [12,1,2]: return "winter"
        if month in [3,4,5]: return "spring"
        if month in [6,7,8]: return "summer"
        return "autumn"

    def _is_greek_holiday(self, ts: datetime):
        d, m, y = ts.day, ts.month, ts.year
        fixed = {(1,1),(1,6),(25,3),(1,5),(15,8),(28,10),(25,12),(26,12)}
        if (d, m) in fixed: return True

        if m == 8 and 8 <= d <= 15: return True
        
        easter = {
            2024: [(3,5), (5,5), (6,5)],
            2025: [(18,4), (20,4), (21,4)],
            2026: [(10,4), (12,4), (13,4)],
        }
        return y in easter and (d, m) in easter[y]

    def _derive_day_of_week(self, ts):
        return (ts.isoweekday() % 7) + 1 # 1 = Monday, 7 = Sunday

    def _derive_is_weekend(self, dow):
        return 1 if dow in (6, 7) else 0 # Assuming 6=Sat, 7=Sun from above

    def _derive_is_peak(self, hour):
        return 1 if (7 <= hour <= 10) or (15 <= hour <= 18) else 0

    # 
    # Public Prediction Function
    # 

    def predict(self, station_index, date_str, time_str, boarding_disembark, weather_score):
        """
        Generates a forecast. Call init() once before using this.

        Args:
            station_index (int): Zero-based index from the SUBWAY_STATIONS list.
            date_str (str): Date in "YYYY-MM-DD" format.
            time_str (str): Time in "HH:MM" format.
            boarding_disembark (str): "b" for boarding, "d" for disembark.
            weather_score (float): A score from 0 to 100.

        Returns:
            tuple: (prediction_int, lower_bound_int, upper_bound_int)
            
        Raises:
            RuntimeError: If the model is not loaded first.
            ValueError: If date/time parsing fails or station_index is invalid.
        """
        if self.model is None:
            raise RuntimeError("Model not loaded. Call init() first.")

        #  3.1 Process Inputs 
        
        # Validate index and get station name
        if not (0 <= station_index < len(self.STATIONS_LIST)):
            raise ValueError(f"Station index {station_index} out of bounds (0-{len(self.STATIONS_LIST)-1}).")
        
        station_name = self.STATIONS_LIST[station_index]

        # Get priors for this station, or global priors if not found
        pri = self.PRIORS.get(station_name, self.GLOBAL_PRIOR)

        ts = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
        
        bd = boarding_disembark.strip().lower()
        is_boarding = 1 if bd == "b" else 0

        weather_score = float(weather_score)
        temperature = 15.0 + (weather_score - 50) * 0.3
        precipitation = max(0.0, (70 - weather_score) * 0.1)
        cloud_cover = min(100.0, max(0.0, 100 - weather_score))
        wind_speed = max(0.0, (100 - weather_score) * 0.1)

        # 3.2 Build Feature Row
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
            "station_hour": f"{station_name}_H{hour}",
            "hour_of_day": hour,
            "day_of_week": dow,
            "month": month,
            "weather_score": weather_score,
            "temperature_2m": temperature,
            "precipitation": precipitation,
            "cloud_cover": cloud_cover,
            "wind_speed_10m": wind_speed,
            "station_mean": pri["station_mean"],
            "station_total": pri["station_total"],
            "station_peak_ratio": pri["station_peak_ratio"],
        }

        # Ensure feature order matches the model's expectation
        X = pd.DataFrame([row])[self.FEATURES]

        # 3.3 Predict
        pred_log = self.model.predict(X)[0]
        pred = np.expm1(pred_log) if self.train_on_log else pred_log
        pred = max(0.0, float(pred))

        mae = self.test_metrics["mae"]
        lower, upper = max(0, pred - mae), pred + mae

        # 3.4 Return Integers
        return (int(pred), int(lower), int(upper))