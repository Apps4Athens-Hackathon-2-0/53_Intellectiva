#!/usr/bin/env python3
"""
Feature Engineering for Pure Forecasting
Adds only calendar features
"""

import pandas as pd
from datetime import date, timedelta

INPUT_CSV = "subway_c.csv"
OUTPUT_CSV = "subway_forecast_ready.csv"

print(f"📥 Loading {INPUT_CSV}...")
df = pd.read_csv(INPUT_CSV, low_memory=False)
original_count = len(df)
print(f"📥 Loaded {original_count} rows")

df["date_hour"] = pd.to_datetime(df["date_hour"])

print("Adding calendar features...")
df["hour_of_day"] = df["date_hour"].dt.hour
df["day_of_week"] = df["date_hour"].dt.dayofweek + 1  # 1=Monday, 7=Sunday
df["month"] = df["date_hour"].dt.month

df["is_weekend"] = df["day_of_week"].isin([6, 7]).astype(int)

def get_season(month):
    if month in [12, 1, 2]: return "winter"
    elif month in [3, 4, 5]: return "spring"
    elif month in [6, 7, 8]: return "summer"
    else: return "autumn"

df["season"] = df["month"].apply(get_season)

df["is_peak_hour"] = (
    ((df["hour_of_day"] >= 7) & (df["hour_of_day"] <= 10)) |
    ((df["hour_of_day"] >= 15) & (df["hour_of_day"] <= 18))
).astype(int)

print("Adding Greek holidays...")
def build_greek_holidays(start_year=2020, end_year=2026):
    holidays = []
    orthodox_easter = {
        2020: date(2020, 4, 19), 2021: date(2021, 5, 2), 2022: date(2022, 4, 24),
        2023: date(2023, 4, 16), 2024: date(2024, 5, 5), 2025: date(2025, 4, 20),
        2026: date(2026, 4, 12),
    }
    for year in range(start_year, end_year + 1):
        easter = orthodox_easter.get(year)
        if not easter: continue
        fixed = [
            date(year, 1, 1), date(year, 1, 6), date(year, 3, 25),
            date(year, 5, 1), date(year, 8, 15), date(year, 10, 28),
            date(year, 12, 25), date(year, 12, 26),
        ]
        easter_related = [
            easter - timedelta(days=48), easter - timedelta(days=2), easter,
            easter + timedelta(days=1), easter + timedelta(days=50),
        ]
        august_holidays = [date(year, 8, d) for d in range(8, 16)]
        holidays.extend(fixed + easter_related + august_holidays)
    return set(holidays)

holiday_dates = build_greek_holidays()
# Create a date-only column for matching
df["local_date"] = df["date_hour"].dt.date
df["is_holiday"] = df["local_date"].isin(holiday_dates).astype(int)
df = df.drop(columns=["local_date"])

df["is_boarding"] = (df["boarding_disembark_desc"] == "Boarding").astype(int)

print(f"✅ Final row count: {len(df)}")

print(f"\n💾 Saving to {OUTPUT_CSV}...")
df.to_csv(OUTPUT_CSV, index=False)
print(f"✅ Saved: {OUTPUT_CSV}")
