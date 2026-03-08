#!/usr/bin/env python3
# python plot.py [--station STATION_NAME] [--save]

import argparse
import json

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from catboost import CatBoostRegressor

MODEL_FILE = "future_forecast_model.cbm"
INFO_FILE  = "future_forecast_info.json"
DATA_FILE  = "subway_forecast_ready.csv"

DEFAULT_STATION = "ΑΕΡΟΔΡΟΜΙΟ"

def load_model_and_meta(model_file: str, info_file: str):
    model = CatBoostRegressor()
    model.load_model(model_file)
    with open(info_file) as f:
        meta = json.load(f)
    return model, meta


def process_direction(
    full_df: pd.DataFrame,
    station: str,
    is_boarding_val: int,
    label: str,
    model,
    meta: dict,
) -> pd.DataFrame | None:
    FEATURES      = meta["features"]
    CATEGORICAL   = meta["categorical"]
    NUMERIC       = meta["numeric"]
    PRIORS        = meta.get("priors", {})
    GLOBAL_PRIOR  = meta.get("global_prior", {})
    MEDIANS       = meta.get("medians", {})

    df = full_df[
        (full_df["dv_platenum_station"] == station) &
        (full_df["is_boarding"] == is_boarding_val)
    ].copy()

    df = df.dropna(subset=["date_hour"]).sort_values("date_hour")
    if df.empty:
        print(f"No data found for {label}.")
        return None

    prior_key = f"{station}_{is_boarding_val}"
    pri = PRIORS.get(prior_key, GLOBAL_PRIOR)
    df["station_mean"]       = pri["station_mean"]
    df["station_total"]      = pri["station_total"]
    df["station_peak_ratio"] = pri["station_peak_ratio"]

    for col in NUMERIC:
        if col in df.columns:
            df[col] = df[col].fillna(MEDIANS.get(col, 0.0))
    for col in CATEGORICAL:
        if col in df.columns:
            df[col] = df[col].astype(str)

    df["pred"] = np.maximum(0, model.predict(df[FEATURES]))

    return (
        df.groupby("hour_of_day")[["dv_validations", "pred"]]
        .mean()
        .reset_index()
        .sort_values("hour_of_day")
        .dropna(subset=["dv_validations", "pred"])
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Plot ridership forecast for a Line C station.")
    parser.add_argument("--station", default=DEFAULT_STATION,
                        help=f"Station name in Greek (default: {DEFAULT_STATION})")
    parser.add_argument("--save", action="store_true",
                        help="Save the plot to a PNG file instead of displaying it")
    args = parser.parse_args()

    station = args.station

    print(f"Loading model and metadata...")
    model, meta = load_model_and_meta(MODEL_FILE, INFO_FILE)

    print(f"Loading dataset...")
    full_df = pd.read_csv(DATA_FILE)
    full_df["date_hour"] = pd.to_datetime(full_df["date_hour"], errors="coerce", utc=True)

    df_embark    = process_direction(full_df, station, 1, "Embark",    model, meta)
    df_disembark = process_direction(full_df, station, 0, "Disembark", model, meta)

    if df_embark is None and df_disembark is None:
        print(f"No data available for station '{station}'. Exiting.")
        return

    fig, ax = plt.subplots(figsize=(18, 8))

    if df_embark is not None:
        ax.plot(df_embark["hour_of_day"], df_embark["dv_validations"],
                color="navy", linestyle="-", linewidth=2, alpha=0.6, label="Actual Embark")
        ax.plot(df_embark["hour_of_day"], df_embark["pred"],
                color="dodgerblue", linestyle="--", linewidth=2, label="Predicted Embark")

    if df_disembark is not None:
        ax.plot(df_disembark["hour_of_day"], df_disembark["dv_validations"],
                color="darkred", linestyle="-", linewidth=2, alpha=0.6, label="Actual Disembark")
        ax.plot(df_disembark["hour_of_day"], df_disembark["pred"],
                color="tomato", linestyle="--", linewidth=2, label="Predicted Disembark")

    ax.set_title(f"{station} — Average Daily Profile by Hour (Actual vs Predicted)", fontsize=16)
    ax.set_xlabel("Hour of Day")
    ax.set_ylabel("Avg Validations")
    ax.grid(True, alpha=0.3)
    ax.legend()
    ax.set_xticks(range(24))
    ax.set_xlim(-0.5, 23.5)
    fig.tight_layout()

    if args.save:
        out_file = f"{station}_forecast.png"
        fig.savefig(out_file, dpi=150)
        print(f"Plot saved to: {out_file}")
    else:
        plt.show()


if __name__ == "__main__":
    main()