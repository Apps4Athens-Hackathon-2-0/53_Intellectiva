#!/usr/bin/env python3
"""
Future Forecasting Model V5
Adds station priors (mean, total, peak_ratio) to fix magnitude errors
Predicts future validations for ANY date/time/station/weather.
"""

import pandas as pd
import numpy as np
from catboost import CatBoostRegressor, Pool
from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    mean_squared_error, mean_absolute_error, r2_score
)
import json

INPUT_CSV = "subway_forecast_ready.csv"
MODEL_FILE = "future_forecast_model.cbm"
FEATURE_INFO_FILE = "future_forecast_info.json"

print("🚇 Training Future Forecast Model V5")
print("=" * 80)

# ----------------------------------------------------------------------
# 1. LOAD DATA
# ----------------------------------------------------------------------

print("\n📥 Loading dataset...")
df = pd.read_csv(INPUT_CSV, low_memory=False)
print(f"   Rows loaded: {len(df):,}")

# ----------------------------------------------------------------------
# 2. STATION PRIORS (NEW!)
# ----------------------------------------------------------------------

print("\n📊 Computing station priors (mean, total, peak ratio)...")

station_stats = df.groupby("dv_platenum_station")["dv_validations"].agg(
    station_mean="mean",
    station_max="max",
    station_total="sum"
).reset_index()

station_stats["station_peak_ratio"] = (
    station_stats["station_max"] / (station_stats["station_mean"] + 1e-9)
)

df = df.merge(station_stats, on="dv_platenum_station", how="left")

print("   ✔ station_mean, station_total, station_peak_ratio added")

# ----------------------------------------------------------------------
# 3. CORE FEATURE: station_hour
# ----------------------------------------------------------------------

print("\n🔧 Adding station-hour interaction...")

df["station_hour"] = (
    df["dv_platenum_station"].astype(str)
    + "_H"
    + df["hour_of_day"].astype(str)
)

print("   ✔ station_hour created")

# ----------------------------------------------------------------------
# 4. FEATURE SET (FUTURE-SAFE)
# ----------------------------------------------------------------------

CATEGORICAL = [
    "dv_platenum_station",
    "is_boarding",
    "season",
    "is_weekend",
    "is_holiday",
    "is_peak_hour",
    "station_hour",
]

NUMERIC = [
    "hour_of_day",
    "day_of_week",
    "month",
    "weather_score",
    "temperature_2m",
    "precipitation",
    "cloud_cover",
    "wind_speed_10m",

    # NEW NUMERIC FEATURES
    "station_mean",
    "station_total",
    "station_peak_ratio",
]

ALL_FEATURES = CATEGORICAL + NUMERIC
TARGET = "dv_validations"

print("\n📊 Using features:")
for f in ALL_FEATURES:
    print("   •", f)

# ----------------------------------------------------------------------
# 5. CLEANING
# ----------------------------------------------------------------------

df = df.dropna(subset=[TARGET])
df = df[df[TARGET] > 0]

for col in NUMERIC:
    df[col] = df[col].fillna(df[col].median())

for col in CATEGORICAL:
    df[col] = df[col].astype(str)

print(f"\n✔ Clean dataset: {len(df):,} rows")

# ----------------------------------------------------------------------
# 6. LOG TARGET
# ----------------------------------------------------------------------

print("\n📈 Log-transforming target...")

df["log_validations"] = np.log1p(df[TARGET])
TARGET_LOG = "log_validations"

# ----------------------------------------------------------------------
# 7. SPLIT
# ----------------------------------------------------------------------

df["hour_bin"] = pd.cut(df["hour_of_day"], bins=6, labels=False)

X = df[ALL_FEATURES].copy()
y_log = df[TARGET_LOG].copy()

X_temp, X_test, y_temp, y_test = train_test_split(
    X, y_log,
    test_size=0.15,
    random_state=42,
    stratify=df["hour_bin"]
)

X_train, X_val, y_train, y_val = train_test_split(
    X_temp, y_temp,
    test_size=0.2,
    random_state=42
)

print(f"\n🔀 Splits:")
print(f"   Train: {len(X_train):,}")
print(f"   Val:   {len(X_val):,}")
print(f"   Test:  {len(X_test):,}")

# ----------------------------------------------------------------------
# 8. TRAIN CATBOOST
# ----------------------------------------------------------------------

print("\n⚡ Training CatBoost...")

train_pool = Pool(X_train, y_train, cat_features=CATEGORICAL)
val_pool = Pool(X_val, y_val, cat_features=CATEGORICAL)

model = CatBoostRegressor(
    iterations=2000,
    learning_rate=0.04,
    depth=8,
    l2_leaf_reg=4,
    loss_function="RMSE",
    eval_metric="RMSE",
    bootstrap_type="Bayesian",
    bagging_temperature=0.5,
    random_seed=42,
    verbose=100,
    early_stopping_rounds=200,
)

model.fit(train_pool, eval_set=val_pool, verbose_eval=100)

print("\n✔ Training complete!")

# ----------------------------------------------------------------------
# 9. EVALUATION
# ----------------------------------------------------------------------

def evaluate(name, y_true_log, y_pred_log):
    y_true = np.expm1(y_true_log)
    y_pred = np.expm1(y_pred_log)

    rmse = np.sqrt(mean_squared_error(y_true, y_pred))
    mae  = mean_absolute_error(y_true, y_pred)
    r2   = r2_score(y_true, y_pred)

    mask = y_true > 10
    mape = (
        np.mean(np.abs((y_true[mask] - y_pred[mask]) / y_true[mask])) * 100
        if mask.sum() else 0
    )

    medape = np.median(np.abs((y_true - y_pred) / y_true)) * 100

    print(f"\n{name}:")
    print(f"   RMSE:   {rmse:.2f}")
    print(f"   MAE:    {mae:.2f}")
    print(f"   MAPE:   {mape:.1f}%")
    print(f"   MedAPE: {medape:.1f}%")
    print(f"   R²:     {r2:.4f}")

    return dict(rmse=rmse, mae=mae, mape=mape, medape=medape, r2=r2)

train_metrics = evaluate("Train", y_train, model.predict(X_train))
val_metrics   = evaluate("Validation", y_val, model.predict(X_val))
test_metrics  = evaluate("Test", y_test, model.predict(X_test))

# ----------------------------------------------------------------------
# 10. FEATURE IMPORTANCE
# ----------------------------------------------------------------------

print("\n🔍 Feature Importance (Top 10):")

imp_df = pd.DataFrame({
    "feature": ALL_FEATURES,
    "importance": model.get_feature_importance(train_pool)
}).sort_values("importance", ascending=False)

print(imp_df.head(10).to_string(index=False))

# ----------------------------------------------------------------------
# 11. SAVE MODEL + METADATA
# ----------------------------------------------------------------------

print("\n💾 Saving model & metadata...")

model.save_model(MODEL_FILE)

meta = {
    "features": ALL_FEATURES,
    "categorical": CATEGORICAL,
    "numeric": NUMERIC,
    "test_metrics": test_metrics,
    "train_on_log_scale": True,
    "top_feature_importances": imp_df.head(15).to_dict("records"),
}

with open(FEATURE_INFO_FILE, "w") as f:
    json.dump(meta, f, indent=2)

print(f"✔ Saved: {MODEL_FILE}")
print(f"✔ Saved: {FEATURE_INFO_FILE}")

print("\n✨ Future Forecast Model V5 Ready!")
print("=" * 80)
