#!/usr/bin/env python3

import pandas as pd
from datetime import date, timedelta

INPUT_CSV  = "subway_c.csv"
OUTPUT_CSV = "subway_forecast_ready.csv"

# Constants

_ORTHODOX_EASTER = {
    2020: date(2020, 4, 19), 2021: date(2021, 5, 2),  2022: date(2022, 4, 24),
    2023: date(2023, 4, 16), 2024: date(2024, 5, 5),  2025: date(2025, 4, 20),
    2026: date(2026, 4, 12),
}

_SEASON_MAP = {
    12: "winter",  1: "winter",  2: "winter",
     3: "spring",  4: "spring",  5: "spring",
     6: "summer",  7: "summer",  8: "summer",
     9: "autumn", 10: "autumn", 11: "autumn",
}

# Right-open bins: [0,6) = night, [6,10) = am_peak, etc.
_HOUR_BUCKET_BINS   = [0, 6, 10, 15, 19, 24]
_HOUR_BUCKET_LABELS = ["night", "am_peak", "midday", "pm_peak", "evening"]


# Holiday helpers

def build_greek_holidays(start_year: int = 2020, end_year: int = 2026) -> dict:
    """
    Return a dict mapping date -> holiday_type string.
    Types: christmas, easter, national_day, summer_closure, other
    """
    holidays: dict = {}
    for year in range(start_year, end_year + 1):
        easter = _ORTHODOX_EASTER.get(year)
        if not easter:
            continue

        holidays[date(year, 1,  1)]  = "other"
        holidays[date(year, 1,  6)]  = "other"
        holidays[date(year, 3, 25)]  = "national_day"
        holidays[date(year, 5,  1)]  = "other"
        holidays[date(year, 8, 15)]  = "other"
        holidays[date(year, 10, 28)] = "national_day"
        holidays[date(year, 12, 25)] = "christmas"
        holidays[date(year, 12, 26)] = "christmas"

        holidays[easter - timedelta(days=48)] = "easter"
        holidays[easter - timedelta(days=2)]  = "easter"
        holidays[easter]                       = "easter"
        holidays[easter + timedelta(days=1)]  = "easter"
        holidays[easter + timedelta(days=50)] = "easter"

        for d in range(8, 16):
            holidays[date(year, 8, d)] = "summer_closure"

    return holidays


# Main

print(f"Loading {INPUT_CSV}...")
df = pd.read_csv(INPUT_CSV, low_memory=False)
print(f"Loaded {len(df):,} rows")

df["date_hour"] = pd.to_datetime(df["date_hour"])

# Base calendar
df["hour_of_day"] = df["date_hour"].dt.hour
df["day_of_week"] = df["date_hour"].dt.dayofweek + 1    # Monday=1, Sunday=7
df["month"]       = df["date_hour"].dt.month
df["is_weekend"]  = (df["day_of_week"] >= 6).astype(int)
df["season"]      = df["month"].map(_SEASON_MAP)
df["is_peak_hour"] = (
    df["hour_of_day"].between(7, 10) | df["hour_of_day"].between(15, 18)
).astype(int)

# Hour bucket — used for stratified priors and as a standalone feature
df["hour_bucket"] = pd.cut(
    df["hour_of_day"],
    bins=_HOUR_BUCKET_BINS,
    labels=_HOUR_BUCKET_LABELS,
    right=False,
).astype(str)

# Holiday type
print("Adding Greek holiday features...")
holiday_map        = build_greek_holidays()
local_dates        = df["date_hour"].dt.date
df["holiday_type"] = local_dates.map(lambda d: holiday_map.get(d, "none"))
df["is_holiday"]   = (df["holiday_type"] != "none").astype(int)

# Station interaction features
station             = df["dv_platenum_station"]
df["station_dow"]   = station + "_" + df["day_of_week"].astype(str)
df["station_hour"]  = station + "_" + df["hour_of_day"].astype(str)
df["station_month"] = station + "_" + df["month"].astype(str)

# Binned weather
df["rain_intensity"] = pd.cut(
    df["precipitation"].fillna(0),
    bins=[-1, 0, 1, 5, 100],
    labels=["none", "light", "moderate", "heavy"],
).astype(str)

df["temp_band"] = pd.cut(
    df["temperature_2m"].fillna(15),
    bins=[-20, 5, 15, 25, 35, 50],
    labels=["cold", "cool", "mild", "warm", "hot"],
).astype(str)

# Direction flag
df["is_boarding"] = (df["boarding_disembark_desc"] == "Boarding").astype(int)

print(f"Final row count: {len(df):,}")
print(f"Saving to {OUTPUT_CSV}...")
df.to_csv(OUTPUT_CSV, index=False)
print(f"Saved: {OUTPUT_CSV}")