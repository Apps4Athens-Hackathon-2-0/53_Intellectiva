#!/usr/bin/env python3
"""
Future Forecasting Model (Methodologically Correct)
- Chronological Time-Based Splitting
- Train-Only Prior and Median calculation (Zero Target Leakage)
- Raw features (No weather_score or station_hour)
- Predicts raw counts directly using RMSE (No expm1 bias)
"""

import pandas as pd
import numpy as np
from catboost import CatBoostRegressor, Pool
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
import json
import os

INPUT_CSV = "subway_forecast_ready.csv"
MODEL_FILE = "future_forecast_model.cbm"
FEATURE_INFO_FILE = "future_forecast_info.json"
TEST_DATA_FILE = "test_data.csv"

print("🚇 Training Future Forecast Model (Methodologically Correct)")
print("=" * 80)

# ----------------------------------------------------------------------
# 1. LOAD DATA
# ----------------------------------------------------------------------
print("\n📥 Loading dataset...")
df = pd.read_csv(INPUT_CSV, low_memory=False)

df["date_hour"] = pd.to_datetime(df["date_hour"], errors="coerce", utc=True)
df = df.dropna(subset=["dv_validations", "date_hour"])
df = df[df["dv_validations"] > 0].copy()

# Sort chronologically for time-based split
df = df.sort_values("date_hour").reset_index(drop=True)
print(f"   Rows loaded & sorted: {len(df):,}")

# ----------------------------------------------------------------------
# 2. CHRONOLOGICAL SPLIT (Prevents Data Leakage)
# ----------------------------------------------------------------------
print("\n🔀 Performing Chronological Split...")
n = len(df)
train_idx = int(n * 0.80)
val_idx   = int(n * 0.90)

train_df = df.iloc[:train_idx].copy()
val_df   = df.iloc[train_idx:val_idx].copy()
test_df  = df.iloc[val_idx:].copy()

print(f"   Train: {train_df['date_hour'].min().date()} to {train_df['date_hour'].max().date()} ({len(train_df):,} rows)")
print(f"   Val:   {val_df['date_hour'].min().date()} to {val_df['date_hour'].max().date()} ({len(val_df):,} rows)")
print(f"   Test:  {test_df['date_hour'].min().date()} to {test_df['date_hour'].max().date()} ({len(test_df):,} rows)")

# ----------------------------------------------------------------------
# 3. COMPUTE SAFE PRIORS (Prevents Target Leakage)
# ----------------------------------------------------------------------
print("\n📊 Computing station priors safely (from Training Set ONLY)...")

station_stats = train_df.groupby(["dv_platenum_station", "is_boarding"])["dv_validations"].agg(
    station_mean="mean",
    station_max="max",
    station_total="sum"
).reset_index()

station_stats["station_peak_ratio"] = (
    station_stats["station_max"] / (station_stats["station_mean"] + 1e-9)
)

global_prior = {
    "station_mean": train_df["dv_validations"].mean(),
    "station_max": train_df["dv_validations"].max(),
    "station_total": train_df["dv_validations"].sum() / train_df["dv_platenum_station"].nunique(),
    "station_peak_ratio": 2.0
}

def add_priors(data):
    res = data.merge(station_stats, on=["dv_platenum_station", "is_boarding"], how="left")
    for col in ["station_mean", "station_max", "station_total", "station_peak_ratio"]:
        res[col] = res[col].fillna(global_prior[col])
    return res

train_df = add_priors(train_df)
val_df   = add_priors(val_df)
test_df  = add_priors(test_df)

# Store priors for predict.py
station_stats["prior_key"] = station_stats["dv_platenum_station"] + "_" + station_stats["is_boarding"].astype(str)
priors_dict = station_stats.set_index("prior_key").drop(columns=["dv_platenum_station", "is_boarding"]).to_dict("index")

# ----------------------------------------------------------------------
# 4. FEATURE SET & IMPUTATION
# ----------------------------------------------------------------------
CATEGORICAL = [
    "dv_platenum_station",
    "is_boarding",
    "season",
    "is_weekend",
    "is_holiday",
    "is_peak_hour"
]

NUMERIC = [
    "hour_of_day",
    "day_of_week",
    "month",
    "temperature_2m",
    "precipitation",
    "cloud_cover",
    "wind_speed_10m",
    "station_mean",
    "station_total",
    "station_peak_ratio"
]

ALL_FEATURES = CATEGORICAL + NUMERIC
TARGET = "dv_validations"

print("\n🔧 Imputing missing data safely (from Training Set ONLY)...")
medians = train_df[NUMERIC].median().to_dict()

def clean_and_impute(data):
    for col in NUMERIC:
        data[col] = data[col].fillna(medians[col])
    for col in CATEGORICAL:
        data[col] = data[col].astype(str)
    return data

train_df = clean_and_impute(train_df)
val_df   = clean_and_impute(val_df)
test_df  = clean_and_impute(test_df)

# Save strictly held-out test data for validate.py
test_df.to_csv(TEST_DATA_FILE, index=False)
print(f"   ✔ Saved prepared test dataset to {TEST_DATA_FILE}")

# ----------------------------------------------------------------------
# 5. TRAIN CATBOOST
# ----------------------------------------------------------------------
print("\n⚡ Training CatBoost (Raw Counts, No Log-Transform Bias)...")

X_train, y_train = train_df[ALL_FEATURES], train_df[TARGET]
X_val, y_val     = val_df[ALL_FEATURES], val_df[TARGET]
X_test, y_test   = test_df[ALL_FEATURES], test_df[TARGET]

train_pool = Pool(X_train, y_train, cat_features=CATEGORICAL)
val_pool   = Pool(X_val, y_val, cat_features=CATEGORICAL)

model = CatBoostRegressor(
    iterations=2000,
    learning_rate=0.04,
    depth=8,
    l2_leaf_reg=4,
    loss_function="RMSE",  # Training directly on counts
    eval_metric="RMSE",
    bootstrap_type="Bayesian",
    bagging_temperature=0.5,
    random_seed=42,
    verbose=200,
    early_stopping_rounds=200,
)

model.fit(train_pool, eval_set=val_pool, verbose_eval=200)

print("\n✔ Training complete!")

# ----------------------------------------------------------------------
# 6. EVALUATION
# ----------------------------------------------------------------------
def evaluate(name, y_true, y_pred):
    y_pred = np.maximum(0, y_pred)  # Clip negative predictions
    rmse = np.sqrt(mean_squared_error(y_true, y_pred))
    mae  = mean_absolute_error(y_true, y_pred)
    r2   = r2_score(y_true, y_pred)

    mask = y_true > 10
    mape = (np.mean(np.abs((y_true[mask] - y_pred[mask]) / y_true[mask])) * 100) if mask.sum() else 0
    medape = np.median(np.abs((y_true - y_pred) / y_true)) * 100

    print(f"\n{name}:")
    print(f"   RMSE:   {rmse:.2f}")
    print(f"   MAE:    {mae:.2f}")
    print(f"   MAPE:   {mape:.1f}%")
    print(f"   MedAPE: {medape:.1f}%")
    print(f"   R²:     {r2:.4f}")
    return dict(rmse=rmse, mae=mae, mape=mape, medape=medape, r2=r2)

train_metrics = evaluate("Train", y_train.values, model.predict(X_train))
val_metrics   = evaluate("Validation", y_val.values, model.predict(X_val))
test_metrics  = evaluate("Test", y_test.values, model.predict(X_test))

# ----------------------------------------------------------------------
# 7. FEATURE IMPORTANCE
# ----------------------------------------------------------------------
print("\n🔍 Feature Importance (Top 10):")
imp_df = pd.DataFrame({
    "feature": ALL_FEATURES,
    "importance": model.get_feature_importance(train_pool)
}).sort_values("importance", ascending=False)
print(imp_df.head(10).to_string(index=False))

# ----------------------------------------------------------------------
# 8. SAVE MODEL + METADATA
# ----------------------------------------------------------------------
print("\n💾 Saving model & metadata...")
model.save_model(MODEL_FILE)

meta = {
    "features": ALL_FEATURES,
    "categorical": CATEGORICAL,
    "numeric": NUMERIC,
    "test_metrics": test_metrics,
    "train_on_log_scale": False,
    "priors": priors_dict,
    "global_prior": global_prior,
    "medians": medians,
}

class NpEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return super(NpEncoder, self).default(obj)

with open(FEATURE_INFO_FILE, "w") as f:
    json.dump(meta, f, indent=2, cls=NpEncoder)

print(f"✔ Saved: {MODEL_FILE}")
print(f"✔ Saved: {FEATURE_INFO_FILE}")
print("\n✨ Future Forecast Model Ready!")
print("=" * 80)
