#!/usr/bin/env python3

import json
import os
import sys
import numpy as np
import pandas as pd
from catboost import CatBoostRegressor
from tabulate import tabulate

MODEL_FILE = "future_forecast_model.cbm"
INFO_FILE  = "future_forecast_info.json"
DATA_FILE  = "test_data.csv"

# Pass/fail thresholds expressed as multiples of the training-phase MAE.
# A cell passes if its MAE < MAE_TOLERANCE_FACTOR * overall_train_mae
# and its MAPE < PASS_MAPE.
MAE_TOLERANCE_FACTOR = 1.5   # allow 50% above training MAE at the cell level
PASS_MAPE            = 35.0  # percent

NON_OPERATING_HOURS = {1, 2, 3, 4, 5, 6}

print("\nEvaluating Future Forecast Model (Test Data Only)")
print("=" * 72)

# Sanity checks
for path in (MODEL_FILE, INFO_FILE, DATA_FILE):
    if not os.path.exists(path):
        print(f"Error: {path} not found. Run train_model.py first.")
        sys.exit(1)

# Load model and metadata
print("\nLoading model and metadata...")
model = CatBoostRegressor()
model.load_model(MODEL_FILE)

with open(INFO_FILE) as f:
    info = json.load(f)

FEATURES     = info["features"]
test_metrics = info["test_metrics"]
PASS_MAE     = test_metrics["mae"] * MAE_TOLERANCE_FACTOR

print(f"  Model loaded")
print(f"  Test MAE from training phase : {test_metrics['mae']:.2f}")
print(f"  Test R2  from training phase : {test_metrics['r2']:.4f}")
print(f"  Cell-level MAE threshold     : {PASS_MAE:.2f}  ({MAE_TOLERANCE_FACTOR}x training MAE)")
print(f"  Cell-level MAPE threshold    : {PASS_MAPE:.1f}%")

# Load test dataset
print("\nLoading test dataset...")
df = pd.read_csv(DATA_FILE, low_memory=False)
print(f"  Loaded {len(df):,} rows")

# Verify all required features are present before attempting inference.
missing = [f for f in FEATURES if f not in df.columns]
if missing:
    print(f"\nError: test_data.csv is missing {len(missing)} feature(s): {missing}")
    print("Re-run train_model.py to regenerate test_data.csv with the current feature set.")
    sys.exit(1)

# Predict
print("\nPredicting on test rows...")
df["pred"] = np.maximum(0, model.predict(df[FEATURES]))

# Aggregate by station x hour, excluding non-operating hours
print("\nAggregating by (station, hour_of_day)...")
df_operating = df[~df["hour_of_day"].isin(NON_OPERATING_HOURS)]

grouped = (
    df_operating
    .groupby(["dv_platenum_station", "hour_of_day"])
    .agg(
        actual_mean=("dv_validations", "mean"),
        pred_mean=("pred", "mean"),
        count=("dv_validations", "size"),
    )
    .reset_index()
)
print(f"  Non-operating hours excluded : {sorted(NON_OPERATING_HOURS)}")
print(f"  Station-hour cells           : {len(grouped):,}")

# Compute errors and pass/fail
grouped["MAE"]  = (grouped["pred_mean"] - grouped["actual_mean"]).abs()
grouped["MAPE"] = (
    grouped["MAE"] / grouped["actual_mean"].replace(0, np.nan) * 100
)
grouped["Result"] = np.where(
    (grouped["MAE"] < PASS_MAE) & (grouped["MAPE"] < PASS_MAPE),
    "PASS", "FAIL",
)

# Per-station summary
station_summary = (
    grouped.groupby("dv_platenum_station")
    .agg(
        mean_MAE=("MAE", "mean"),
        mean_MAPE=("MAPE", "mean"),
        pass_rate=("Result", lambda x: (x == "PASS").mean() * 100),
    )
    .reset_index()
    .sort_values("mean_MAE", ascending=False)
)

print("\nPer-station summary (worst MAE first):\n")
print(tabulate(
    station_summary,
    headers=["Station", "Mean MAE", "Mean MAPE %", "Pass Rate %"],
    floatfmt=".2f",
    tablefmt="fancy_grid",
))

# Overall summary
overall_mae  = grouped["MAE"].mean()
overall_mape = grouped["MAPE"].mean()
overall_pass = (grouped["Result"] == "PASS").mean() * 100

print("\nOverall summary (unseen test data):\n")
print(tabulate(
    [
        ["Overall MAE",               f"{overall_mae:.2f}"],
        ["Overall MAPE",              f"{overall_mape:.1f}%"],
        ["Pass Rate",                 f"{overall_pass:.1f}%"],
        ["Stations evaluated",        grouped["dv_platenum_station"].nunique()],
        ["Station-hour combinations", len(grouped)],
        ["MAE threshold used",        f"{PASS_MAE:.2f}"],
        ["MAPE threshold used",       f"{PASS_MAPE:.1f}%"],
    ],
    headers=["Metric", "Value"],
    tablefmt="fancy_grid",
))

print("\nEvaluation complete.\n")