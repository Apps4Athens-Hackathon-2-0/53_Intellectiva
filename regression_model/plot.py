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
PRIORS = meta.get("priors", {})
GLOBAL_PRIOR = meta.get("global_prior", {})
MEDIANS = meta.get("medians", {})

print("Model loaded")

# LOAD DATA
print("\nLoading dataset to run predictions across full timeline...")
full_df = pd.read_csv(DATA_FILE)
full_df["date_hour"] = pd.to_datetime(full_df["date_hour"], errors="coerce", utc=True)

def process_direction(is_boarding_val, label):
    print(f"\nProcessing {label}...")
    
    df = full_df[
        (full_df["dv_platenum_station"] == STATION) & 
        (full_df["is_boarding"] == is_boarding_val)
    ].copy()
    
    df = df.dropna(subset=["date_hour"]).sort_values("date_hour")
    
    if len(df) == 0:
        print(f"No data found for {label}")
        return None

    # Load safe priors learned during training
    prior_key = f"{STATION}_{is_boarding_val}"
    pri = PRIORS.get(prior_key, GLOBAL_PRIOR)
    df["station_mean"] = pri["station_mean"]
    df["station_total"] = pri["station_total"]
    df["station_peak_ratio"] = pri["station_peak_ratio"]

    # Fill NaNs safely based on training medians
    for col in NUMERIC:
        if col in df.columns:
            df[col] = df[col].fillna(MEDIANS.get(col, 0.0))

    for col in CATEGORICAL:
        if col in df.columns:
            df[col] = df[col].astype(str)

    # Predict raw counts
    df["pred"] = np.maximum(0, model.predict(df[FEATURES]))

    # Aggregate by Hour of Day
    df_hourly_avg = df.groupby("hour_of_day")[["dv_validations", "pred"]].mean().reset_index()
    df_hourly_avg = df_hourly_avg.sort_values("hour_of_day")
    
    return df_hourly_avg.dropna(subset=["dv_validations", "pred"])


# RUN PROCESSING
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
plt.xticks(range(0, 24))
plt.xlim(-0.5, 23.5)

plt.tight_layout()
plt.show()
