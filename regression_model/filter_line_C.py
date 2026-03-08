#!/usr/bin/env python3

import pandas as pd
from predict import SUBWAY_STATIONS

INPUT_FILE  = "oasa_weather_enriched.csv"
OUTPUT_FILE = "subway_c.csv"
SUBWAY_AGENCY = 2

print(f"Loading {INPUT_FILE}...")
df = pd.read_csv(INPUT_FILE, low_memory=False)
print(f"Total records: {len(df):,}")

print("Filtering to Line C subway stations (dv_agency=2)...")
subway_df = df[
    (df["dv_agency"] == SUBWAY_AGENCY) &
    (df["dv_platenum_station"].isin(SUBWAY_STATIONS))
].copy()

print(f"Records retained: {len(subway_df):,}")

assert len(subway_df) > 0, (
    "Filter produced an empty dataset. "
    "Check that dv_agency and station names match the source data."
)

print(f"Saving to {OUTPUT_FILE}...")
subway_df.to_csv(OUTPUT_FILE, index=False)
print(f"Done. Saved: {OUTPUT_FILE}")