#!/usr/bin/env python3
"""
evaluate_model_v5.py
Evaluates the future forecast model using clean station × hour metrics.
Fully aligned with the V5 training script (station priors included).
Pretty printed tables + PASS/FAIL per station-hour.
"""

import pandas as pd
import numpy as np
from catboost import CatBoostRegressor
from tabulate import tabulate
import json

MODEL_FILE = "future_forecast_model.cbm"
INFO_FILE  = "future_forecast_info.json"
DATA_FILE  = "subway_forecast_ready.csv"

print("\n🚇 Evaluating Future Forecast Model V5")
print("=" * 72)

# ---------------------------------------------------------------------
# 1. Load model + metadata
# ---------------------------------------------------------------------
print("\n📦 Loading model & metadata...")

model = CatBoostRegressor()
model.load_model(MODEL_FILE)

with open(INFO_FILE) as f:
    info = json.load(f)

FEATURES     = info["features"]
CATEGORICAL  = info["categorical"]
NUMERIC      = info["numeric"]
LOG_TARGET   = info["train_on_log_scale"]

print("   ✔ Model loaded")
print(f"   ✔ Features: {len(FEATURES)}")
print(f"   ✔ Test R²: {info['test_metrics']['r2']:.4f}")

# ---------------------------------------------------------------------
# 2. Load dataset
# ---------------------------------------------------------------------
print("\n📥 Loading dataset...")
df = pd.read_csv(DATA_FILE, low_memory=False)
print(f"   ✔ Loaded {len(df):,} rows")

# ---------------------------------------------------------------------
# 3. Rebuild training-era features (MUST MATCH TRAINING)
# ---------------------------------------------------------------------

print("\n🔧 Rebuilding features exactly as in training...")

# Keep only positive validation rows
df = df[df["dv_validations"] > 0].copy()

# -------------------------------
# Station priors
# -------------------------------
station_stats = df.groupby("dv_platenum_station")["dv_validations"].agg(
    station_mean="mean",
    station_max="max",
    station_total="sum"
).reset_index()

station_stats["station_peak_ratio"] = (
    station_stats["station_max"] / (station_stats["station_mean"] + 1e-9)
)

df = df.merge(station_stats, on="dv_platenum_station", how="left")

# -------------------------------
# station_hour
# -------------------------------
df["station_hour"] = (
    df["dv_platenum_station"].astype(str) +
    "_H" +
    df["hour_of_day"].astype(str)
)

# -------------------------------
# Fill numeric NaN
# -------------------------------
for col in NUMERIC:
    df[col] = df[col].fillna(df[col].median())

# -------------------------------
# Cast categoricals
# -------------------------------
for col in CATEGORICAL:
    df[col] = df[col].astype(str)

print(f"   ✔ Cleaned & rebuilt rows: {len(df):,}")

# ---------------------------------------------------------------------
# 4. Predict
# ---------------------------------------------------------------------

print("\n🔮 Predicting on all rows...")

pred_log = model.predict(df[FEATURES])
df["pred"] = np.expm1(pred_log) if LOG_TARGET else pred_log
df["pred"] = df["pred"].clip(lower=0)

# ---------------------------------------------------------------------
# 5. Aggregate: station × hour
# ---------------------------------------------------------------------

print("\n📊 Aggregating by (station, hour_of_day)...")

grouped = (
    df.groupby(["dv_platenum_station", "hour_of_day"])
      .agg(
          actual_mean=("dv_validations", "mean"),
          pred_mean=("pred", "mean"),
          count=("dv_validations", "size")
      )
      .reset_index()
)

# ---------------------------------------------------------------------
# 5.1 REMOVE NON-OPERATING HOURS 1–6
# ---------------------------------------------------------------------
# Athens metro is not running: ignore these hours entirely from evaluation
NON_OPERATING_HOURS = [1, 2, 3, 4, 5, 6]

grouped = grouped[~grouped["hour_of_day"].isin(NON_OPERATING_HOURS)].copy()

print(f"   ✔ Removed non-operating hours {NON_OPERATING_HOURS}")
print(f"   ✔ Rows after filtering: {len(grouped):,}")

# ---------------------------------------------------------------------
# 6. Compute Errors
# ---------------------------------------------------------------------

grouped["MAE"]  = (grouped["pred_mean"] - grouped["actual_mean"]).abs()
grouped["MAPE"] = grouped["MAE"] / grouped["actual_mean"].replace(0, np.nan) * 100

# ---------------------------------------------------------------------
# 6. PASS/FAIL criteria
# ---------------------------------------------------------------------

PASS_MAE  = 180
PASS_MAPE = 35

grouped["Result"] = np.where(
    (grouped["MAE"] < PASS_MAE) & (grouped["MAPE"] < PASS_MAPE),
    "PASS", "FAIL"
)


# ---------------------------------------------------------------------
# 6. PASS/FAIL criteria
# ---------------------------------------------------------------------

PASS_MAE  = 180
PASS_MAPE = 35

grouped["Result"] = np.where(
    (grouped["MAE"] < PASS_MAE) & (grouped["MAPE"] < PASS_MAPE),
    "PASS", "FAIL"
)

# ---------------------------------------------------------------------
# 7. Print sample
# ---------------------------------------------------------------------

print("\n📋 Sample Output (first 25 rows):\n")

sample = grouped.head(25)[[
    "dv_platenum_station", "hour_of_day",
    "actual_mean", "pred_mean",
    "MAE", "MAPE", "count", "Result"
]]

print(tabulate(
    sample,
    headers="keys",
    floatfmt=".2f",
    tablefmt="fancy_grid"
))

# ---------------------------------------------------------------------
# 8. Summary
# ---------------------------------------------------------------------

overall_mae = grouped["MAE"].mean()
overall_mape = grouped["MAPE"].mean()
overall_pass = (grouped["Result"] == "PASS").mean() * 100

print("\n📈 OVERALL SUMMARY\n")

summary = [
    ["Overall MAE", f"{overall_mae:.2f}"],
    ["Overall MAPE", f"{overall_mape:.1f}%"],
    ["Pass Rate", f"{overall_pass:.1f}%"],
    ["Stations", grouped['dv_platenum_station'].nunique()],
    ["Station-Hour Rows", len(grouped)]
]

print(tabulate(
    summary,
    headers=["Metric", "Value"],
    tablefmt="fancy_grid"
))

print("\n✨ Evaluation Complete!\n")