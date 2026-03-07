#!/usr/bin/env python3
"""
validate.py
Evaluates the future forecast model strictly on the held-out TEST set.
Ensures zero data leakage during evaluation.
"""

import pandas as pd
import numpy as np
from catboost import CatBoostRegressor
from tabulate import tabulate
import json
import os

MODEL_FILE = "future_forecast_model.cbm"
INFO_FILE  = "future_forecast_info.json"
DATA_FILE  = "test_data.csv"

print("\n🚇 Evaluating Future Forecast Model (Test Data Only)")
print("=" * 72)

if not os.path.exists(DATA_FILE):
    print(f"❌ Error: {DATA_FILE} not found. Please run train_model.py first.")
    exit(1)

# ---------------------------------------------------------------------
# 1. Load model + metadata
# ---------------------------------------------------------------------
print("\n📦 Loading model & metadata...")
model = CatBoostRegressor()
model.load_model(MODEL_FILE)

with open(INFO_FILE) as f:
    info = json.load(f)

FEATURES = info["features"]
print("   ✔ Model loaded")
print(f"   ✔ Test R² from training phase: {info['test_metrics']['r2']:.4f}")

# ---------------------------------------------------------------------
# 2. Load strictly unseen test dataset
# ---------------------------------------------------------------------
print("\n📥 Loading unseen test dataset...")
df = pd.read_csv(DATA_FILE, low_memory=False)
print(f"   ✔ Loaded {len(df):,} test rows")

# ---------------------------------------------------------------------
# 3. Predict
# ---------------------------------------------------------------------
print("\n🔮 Predicting on test rows...")
pred = model.predict(df[FEATURES])
df["pred"] = np.maximum(0, pred)  # Clip negative predictions

# ---------------------------------------------------------------------
# 4. Aggregate: station × hour
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
# 5. REMOVE NON-OPERATING HOURS 1–6
# ---------------------------------------------------------------------
NON_OPERATING_HOURS = [1, 2, 3, 4, 5, 6]
grouped = grouped[~grouped["hour_of_day"].isin(NON_OPERATING_HOURS)].copy()

print(f"   ✔ Removed non-operating hours {NON_OPERATING_HOURS}")
print(f"   ✔ Rows after filtering: {len(grouped):,}")

# ---------------------------------------------------------------------
# 6. Compute Errors
# ---------------------------------------------------------------------
grouped["MAE"]  = (grouped["pred_mean"] - grouped["actual_mean"]).abs()
grouped["MAPE"] = grouped["MAE"] / grouped["actual_mean"].replace(0, np.nan) * 100

# PASS/FAIL criteria
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

print("\n📈 OVERALL SUMMARY (Unseen Test Data)\n")
summary = [
    ["Overall MAE", f"{overall_mae:.2f}"],
    ["Overall MAPE", f"{overall_mape:.1f}%"],
    ["Pass Rate", f"{overall_pass:.1f}%"],
    ["Stations Evaluated", grouped['dv_platenum_station'].nunique()],
    ["Station-Hour Combinations", len(grouped)]
]

print(tabulate(
    summary,
    headers=["Metric", "Value"],
    tablefmt="fancy_grid"
))

print("\n✨ Evaluation Complete!\n")
