#!/usr/bin/env python3

import pandas as pd

OASA_FILE    = "oasa_raw_data.csv"
WEATHER_FILE = "weather_athens_hourly.csv"
OUTPUT_FILE  = "oasa_weather_enriched.csv"

WEATHER_COLS = ["temperature_2m", "precipitation", "rain",
                "cloud_cover", "wind_speed_10m", "weather_code"]

print("Loading OASA data...")
oasa = pd.read_csv(OASA_FILE, low_memory=False)
print(f"OASA rows: {len(oasa):,}")

print("Loading weather data...")
weather = pd.read_csv(WEATHER_FILE)
print(f"Weather rows (raw): {len(weather):,}")

print("Normalizing timestamps...")
oasa["date_hour"]    = pd.to_datetime(oasa["date_hour"],    errors="coerce").dt.floor("h")
weather["date_hour"] = pd.to_datetime(weather["date"],      errors="coerce").dt.floor("h")
weather = weather.drop(columns=["date"])

print("Removing duplicate weather hours...")
before = len(weather)
weather = weather.drop_duplicates(subset=["date_hour"])
print(f"Weather unique hours: {len(weather):,} ({before - len(weather):,} duplicates removed)")

print("Merging datasets (left join on date_hour)...")
merged = oasa.merge(weather, on="date_hour", how="left")
print(f"Merged rows: {len(merged):,}")

# Warn if any OASA rows could not be matched to weather data.
unmatched = merged[WEATHER_COLS].isna().any(axis=1).sum()
if unmatched:
    pct = unmatched / len(merged) * 100
    print(f"WARNING: {unmatched:,} rows ({pct:.1f}%) have no weather match — "
          "check that weather date range covers all OASA timestamps.")
else:
    print("All OASA rows matched to weather data.")

print(f"Saving to {OUTPUT_FILE}...")
merged.to_csv(OUTPUT_FILE, index=False)
print(f"Done. Saved: {OUTPUT_FILE}")