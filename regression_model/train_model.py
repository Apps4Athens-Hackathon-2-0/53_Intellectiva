#!/usr/bin/env python3
"""
Trains the Athens Metro Line C ridership forecast model.
- Fixed date-based chronological split (no data leakage)
- Nov–Dec 2025 anomaly period excluded from val and test
- Station priors stratified by hour bucket (training set only)
- CatBoost RMSE on raw validation counts
"""

import json
import sys

import numpy as np
import pandas as pd
from catboost import CatBoostRegressor, Pool
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

INPUT_CSV         = "subway_forecast_ready.csv"
MODEL_FILE        = "future_forecast_model.cbm"
FEATURE_INFO_FILE = "future_forecast_info.json"
TEST_DATA_FILE    = "test_data.csv"

# Split boundaries — adjust if the dataset extends further.
TRAIN_END = pd.Timestamp("2025-07-01", tz="UTC")
VAL_END   = pd.Timestamp("2025-11-01", tz="UTC")

# Nov–Dec 2025: structural ridership anomaly with no precedent in training data.
# Including this period in val or test would corrupt early stopping and
# make evaluation metrics unrepresentative of normal operating conditions.
ANOMALY_START = pd.Timestamp("2025-11-01", tz="UTC")
ANOMALY_END   = pd.Timestamp("2026-01-01", tz="UTC")

# Hour bucket definition — must stay in sync with add_features.py and predict.py
_HOUR_BUCKET_BINS   = [0, 6, 10, 15, 19, 24]
_HOUR_BUCKET_LABELS = ["night", "am_peak", "midday", "pm_peak", "evening"]

print("Training Future Forecast Model")
print("=" * 80)

# ----------------------------------------------------------------------
# 1. Load data
# ----------------------------------------------------------------------
print("\nLoading dataset...")
df = pd.read_csv(INPUT_CSV, low_memory=False)
df["date_hour"] = pd.to_datetime(df["date_hour"], errors="coerce", utc=True)
df = df.dropna(subset=["dv_validations", "date_hour"])
df = df[df["dv_validations"] > 0].copy()
df = df.sort_values("date_hour").reset_index(drop=True)
print(f"Rows loaded and sorted: {len(df):,}")

# ----------------------------------------------------------------------
# 2. Exclude anomaly period
# ----------------------------------------------------------------------
anomaly_mask = (df["date_hour"] >= ANOMALY_START) & (df["date_hour"] < ANOMALY_END)
n_excluded   = anomaly_mask.sum()
df = df[~anomaly_mask].reset_index(drop=True)
print(f"Excluded {n_excluded:,} rows ({ANOMALY_START.date()} to {ANOMALY_END.date()}) "
      f"— Nov/Dec 2025 structural anomaly.")

# Ensure hour_bucket is present
if "hour_bucket" not in df.columns:
    df["hour_bucket"] = pd.cut(
        df["hour_of_day"],
        bins=_HOUR_BUCKET_BINS,
        labels=_HOUR_BUCKET_LABELS,
        right=False,
    ).astype(str)

# ----------------------------------------------------------------------
# 3. Fixed date-based chronological split
# ----------------------------------------------------------------------
print("\nPerforming chronological split...")
train_df = df[df["date_hour"] <  TRAIN_END].copy()
val_df   = df[(df["date_hour"] >= TRAIN_END) & (df["date_hour"] < VAL_END)].copy()
test_df  = df[df["date_hour"] >= VAL_END].copy()

for name, part in [("Train", train_df), ("Val", val_df), ("Test", test_df)]:
    if len(part) == 0:
        print(f"  {name}: EMPTY")
    else:
        print(f"  {name}: {part['date_hour'].min().date()} to "
              f"{part['date_hour'].max().date()} ({len(part):,} rows)")

if len(train_df) == 0:
    print("Error: training set is empty. Check TRAIN_END boundary.")
    sys.exit(1)

if len(val_df) == 0:
    print("Warning: validation set is empty. Early stopping will not function. "
          "Adjust TRAIN_END or VAL_END.")

# If test set is empty (no post-anomaly data available yet), evaluation is
# deferred. A test_data.csv with zero rows is still written so validate.py
# can report a clear message rather than crashing.
if len(test_df) == 0:
    print("Warning: test set is empty — no post-anomaly data available yet. "
          "Final evaluation deferred until post-Jan 2026 data is collected.")

# ----------------------------------------------------------------------
# 4. Station priors stratified by hour bucket (training set only)
# ----------------------------------------------------------------------
print("\nComputing stratified station priors from training set...")

station_stats = (
    train_df.groupby(["dv_platenum_station", "is_boarding", "hour_bucket"])["dv_validations"]
    .agg(station_mean="mean", station_total="sum", station_max="max")
    .reset_index()
)
station_stats["station_peak_ratio"] = (
    station_stats["station_max"] / (station_stats["station_mean"] + 1e-9)
)

global_prior = {
    "station_mean":       float(train_df["dv_validations"].mean()),
    "station_total":      float(train_df["dv_validations"].sum()
                               / train_df["dv_platenum_station"].nunique()),
    "station_peak_ratio": 2.0,
}


def add_priors(data: pd.DataFrame) -> pd.DataFrame:
    data = data.merge(
        station_stats[["dv_platenum_station", "is_boarding", "hour_bucket",
                        "station_mean", "station_total", "station_peak_ratio"]],
        on=["dv_platenum_station", "is_boarding", "hour_bucket"],
        how="left",
    )
    for col, default in global_prior.items():
        data[col] = data[col].fillna(default)
    return data


train_df = add_priors(train_df)
val_df   = add_priors(val_df)
test_df  = add_priors(test_df)

# Serialise priors for predict.py — keyed by station_isboarding_hourbucket
station_stats["prior_key"] = (
    station_stats["dv_platenum_station"] + "_"
    + station_stats["is_boarding"].astype(str) + "_"
    + station_stats["hour_bucket"].astype(str)
)
priors_dict = (
    station_stats.set_index("prior_key")
    [["station_mean", "station_total", "station_peak_ratio"]]
    .to_dict("index")
)

# ----------------------------------------------------------------------
# 5. Features and imputation
# ----------------------------------------------------------------------
CATEGORICAL = [
    "dv_platenum_station",
    "is_boarding",
    "season",
    "is_weekend",
    "is_holiday",
    "is_peak_hour",
    "hour_bucket",
    "holiday_type",
    "station_dow",
    "station_hour",
    "station_month",
    "rain_intensity",
    "temp_band",
]

NUMERIC = [
    "hour_of_day",
    "day_of_week",
    "month",
    "temperature_2m",
    "precipitation",
    "cloud_cover",
    "wind_speed_10m",
    "routes_per_hour",
    "station_mean",
    "station_total",
    "station_peak_ratio",
]

ALL_FEATURES = CATEGORICAL + NUMERIC
TARGET       = "dv_validations"

print("\nImputing missing values from training set medians...")
medians = train_df[NUMERIC].median().to_dict()


def clean(data: pd.DataFrame) -> pd.DataFrame:
    for col in NUMERIC:
        if col in data.columns:
            data[col] = pd.to_numeric(data[col], errors="coerce").fillna(medians[col])
        else:
            data[col] = medians[col]
    for col in CATEGORICAL:
        if col in data.columns:
            data[col] = data[col].fillna("unknown").astype(str)
        else:
            data[col] = "unknown"
    return data


train_df = clean(train_df)
val_df   = clean(val_df)
test_df  = clean(test_df)

# Save after all transforms so validate.py needs no additional processing.
test_df.to_csv(TEST_DATA_FILE, index=False)
print(f"Saved held-out test set to {TEST_DATA_FILE} ({len(test_df):,} rows)")

# ----------------------------------------------------------------------
# 6. Train CatBoost
# ----------------------------------------------------------------------
print("\nTraining CatBoost...")
X_train, y_train = train_df[ALL_FEATURES], train_df[TARGET]
X_val,   y_val   = val_df[ALL_FEATURES],   val_df[TARGET]
X_test,  y_test  = test_df[ALL_FEATURES],  test_df[TARGET]

train_pool = Pool(X_train, y_train, cat_features=CATEGORICAL)

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
    verbose=200,
    early_stopping_rounds=200,
)

if len(val_df) > 0:
    val_pool = Pool(X_val, y_val, cat_features=CATEGORICAL)
    model.fit(train_pool, eval_set=val_pool, verbose_eval=200)
else:
    # No validation set — train to fixed iterations without early stopping.
    print("No validation set available. Training to fixed iterations.")
    model.fit(train_pool, verbose_eval=200)

print("Training complete.")

# ----------------------------------------------------------------------
# 7. Evaluation
# ----------------------------------------------------------------------
def evaluate(name: str, y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    y_pred  = np.maximum(0, y_pred)
    rmse    = float(np.sqrt(mean_squared_error(y_true, y_pred)))
    mae     = float(mean_absolute_error(y_true, y_pred))
    r2      = float(r2_score(y_true, y_pred))

    mask    = y_true > 10
    mape    = float(np.mean(np.abs((y_true[mask] - y_pred[mask]) / y_true[mask])) * 100) \
              if mask.sum() > 0 else float("nan")
    nonzero = y_true != 0
    medape  = float(np.median(np.abs((y_true[nonzero] - y_pred[nonzero]) / y_true[nonzero])) * 100) \
              if nonzero.sum() > 0 else float("nan")

    print(f"\n{name}:")
    print(f"  RMSE:   {rmse:.2f}")
    print(f"  MAE:    {mae:.2f}")
    print(f"  MAPE:   {mape:.1f}%")
    print(f"  MedAPE: {medape:.1f}%")
    print(f"  R2:     {r2:.4f}")
    return dict(rmse=rmse, mae=mae, mape=mape, medape=medape, r2=r2)


evaluate("Train",      y_train.values, model.predict(X_train))

if len(val_df) > 0:
    evaluate("Validation", y_val.values, model.predict(X_val))

test_metrics = (
    evaluate("Test", y_test.values, model.predict(X_test))
    if len(test_df) > 0
    else {"rmse": None, "mae": None, "mape": None, "medape": None, "r2": None}
)

if test_metrics["mae"] is None:
    print("\nTest metrics unavailable — test set is empty.")

# ----------------------------------------------------------------------
# 8. Feature importance
# ----------------------------------------------------------------------
print("\nFeature Importance (Top 15):")
imp_df = (
    pd.DataFrame({
        "feature":    ALL_FEATURES,
        "importance": model.get_feature_importance(train_pool),
    })
    .sort_values("importance", ascending=False)
)
print(imp_df.head(15).to_string(index=False))

# ----------------------------------------------------------------------
# 9. Save model and metadata
# ----------------------------------------------------------------------
print("\nSaving model and metadata...")
model.save_model(MODEL_FILE)


class NpEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.integer):  return int(obj)
        if isinstance(obj, np.floating): return float(obj)
        if isinstance(obj, np.ndarray):  return obj.tolist()
        return super().default(obj)


meta = {
    "features":           ALL_FEATURES,
    "categorical":        CATEGORICAL,
    "numeric":            NUMERIC,
    "test_metrics":       test_metrics,
    "train_on_log_scale": False,
    "priors":             priors_dict,
    "global_prior":       global_prior,
    "medians":            medians,
    "hour_bucket_bins":   _HOUR_BUCKET_BINS,
    "hour_bucket_labels": _HOUR_BUCKET_LABELS,
    "split_boundaries": {
        "train_end":    str(TRAIN_END.date()),
        "val_end":      str(VAL_END.date()),
        "anomaly_start": str(ANOMALY_START.date()),
        "anomaly_end":   str(ANOMALY_END.date()),
    },
}
with open(FEATURE_INFO_FILE, "w") as f:
    json.dump(meta, f, indent=2, cls=NpEncoder)

print(f"Saved: {MODEL_FILE}")
print(f"Saved: {FEATURE_INFO_FILE}")
print("\nFuture Forecast Model ready.")
print("=" * 80)