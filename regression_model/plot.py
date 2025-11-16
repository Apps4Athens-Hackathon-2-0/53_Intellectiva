#!/usr/bin/env python3

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from catboost import CatBoostRegressor
import json

MODEL_FILE = "future_forecast_model.cbm"
INFO_FILE = "future_forecast_info.json"
DATA_FILE = "subway_forecast_ready.csv"

STATION = "ΑΕΡΟΔΡΟΜΙΟ"

print("\nLoading model + metadata...")
model = CatBoostRegressor()
model.load_model(MODEL_FILE)

with open(INFO_FILE) as f:
    meta = json.load(f)

FEATURES = meta["features"]
CATEGORICAL = meta["categorical"]
NUMERIC = meta["numeric"]
LOG_TARGET = meta["train_on_log_scale"]

print("Model loaded")


# LOAD DATA & BUILD PRIORS
print("\nLoading dataset & Building Priors...")
full_df = pd.read_csv(DATA_FILE)
full_df["date_hour"] = pd.to_datetime(full_df["date_hour"], errors="coerce", utc=True)

# Build Priors from the FULL dataset before filtering
station_stats = full_df.groupby("dv_platenum_station")["dv_validations"].agg(
    station_mean="mean",
    station_max="max",
    station_total="sum"
).reset_index()

station_stats["station_peak_ratio"] = (
    station_stats["station_max"] / (station_stats["station_mean"] + 1e-9)
)

# PROCESS FUNCTION
def process_direction(is_boarding_val, label):
    print(f"\nProcessing {label}...")
    
    # 1. Filter
    df = full_df[
        (full_df["dv_platenum_station"] == STATION) & 
        (full_df["is_boarding"] == is_boarding_val)
    ].copy()
    
    df = df.dropna(subset=["date_hour"]).sort_values("date_hour")
    
    # 2. Merge Priors
    df = df.merge(station_stats, on="dv_platenum_station", how="left")
    
    # 3. Rebuild Feature: station_hour
    df["station_hour"] = df["dv_platenum_station"].astype(str) + "_H" + df["hour_of_day"].astype(str)

    # 4. Fill NaNs / Type Conversion
    for col in NUMERIC:
        if col in df.columns:
            df[col] = df[col].fillna(df[col].median())

    for col in CATEGORICAL:
        if col in df.columns:
            df[col] = df[col].astype(str)

    # 5. Predict
    if len(df) == 0:
        print(f"No data found for {label}")
        return None

    pred_log = model.predict(df[FEATURES])
    df["pred"] = np.expm1(pred_log) if LOG_TARGET else pred_log
    df["pred"] = df["pred"].clip(lower=0)

    # 6. Aggregate by Hour of Day
    # This finds the average for each hour (avg for 00:00, avg for 01:00)
    # across all days in the dataset.
    df_hourly_avg = df.groupby("hour_of_day")[["dv_validations", "pred"]].mean().reset_index()
    df_hourly_avg = df_hourly_avg.sort_values("hour_of_day")
    
    return df_hourly_avg.dropna(subset=["dv_validations", "pred"])


# RUN PROCESSING
# 1 = Boarding (Embark), 0 = Disembarking (Disembark)
df_embark = process_direction(1, "Embark (Boarding)")
df_disembark = process_direction(0, "Disembark (Exiting)")


# PLOT
print("\n📈 Plotting 4 lines...")
plt.figure(figsize=(18, 8))

# Embark Lines
if df_embark is not None:
    plt.plot(df_embark["hour_of_day"], df_embark["dv_validations"], 
             color="navy", linestyle="-", linewidth=2, alpha=0.6, 
             label="Actual Embark")
    
    plt.plot(df_embark["hour_of_day"], df_embark["pred"], 
             color="dodgerblue", linestyle="--", linewidth=2, 
             label="Predicted Embark")

# Disembark Lines
if df_disembark is not None:
    plt.plot(df_disembark["hour_of_day"], df_disembark["dv_validations"], 
             color="darkred", linestyle="-", linewidth=2, alpha=0.6, 
             label="Actual Disembark")
    
    plt.plot(df_disembark["hour_of_day"], df_disembark["pred"], 
             color="tomato", linestyle="--", linewidth=2, 
             label="Predicted Disembark")

plt.title(f"{STATION} — Average Daily Profile by Hour (Actual vs Predicted)", fontsize=16)
plt.xlabel("Hour of Day")
plt.ylabel("Avg Validations for that Hour")
plt.grid(True, alpha=0.3)
plt.legend()
plt.xticks(range(0, 24)) # Set x-axis ticks to show every hour
plt.xlim(-0.5, 23.5) # Set x-axis limits

plt.tight_layout()
plt.show()