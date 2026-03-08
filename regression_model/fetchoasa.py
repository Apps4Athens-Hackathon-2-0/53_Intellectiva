#!/usr/bin/env python3
"""
Fetches OASA ridership validation data from data.gov.gr in date chunks.
Output: oasa_raw_data.csv
"""

import csv
import time
import requests
from datetime import datetime, timedelta
from tqdm import tqdm

RIDERSHIP_API  = "https://data.gov.gr/api/v1/query/oasa_ridership"
STARTING_DAY   = datetime(2020, 8, 8)
LAST_DAY       = datetime.today()
CHUNK_SIZE     = 5
MAX_RETRIES    = 3
RETRY_DELAY    = 5
CSV_FILENAME   = "oasa_raw_data.csv"

FIELDNAMES = [
    "dv_agency", "dv_platenum_station", "dv_validations", "dv_route",
    "routes_per_hour", "load_dt", "date_hour", "etl_extraction_dt",
    "etl_load_dt", "dv_agency_desc", "boarding_disembark_desc",
]


def get_ridership_data(from_date: datetime, to_date: datetime) -> list:
    """Fetch ridership records for a date range. Returns empty list on failure."""
    params = {
        "date_from": from_date.strftime("%Y-%m-%d"),
        "date_to":   to_date.strftime("%Y-%m-%d"),
    }
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.get(RIDERSHIP_API, params=params, timeout=30)
            resp.raise_for_status()
            result = resp.json()
            if isinstance(result, dict):
                print(f"\nAPI error response: {result}")
                return []
            return result
        except Exception as exc:
            if attempt < MAX_RETRIES:
                print(f"\nAttempt {attempt} failed ({exc}). Retrying in {RETRY_DELAY}s...")
                time.sleep(RETRY_DELAY)
            else:
                print(f"\nAll {MAX_RETRIES} attempts failed for "
                      f"{from_date.date()} – {to_date.date()}: {exc}")
                return []


def ensure_header(filepath: str) -> None:
    try:
        open(filepath, "r").close()
    except FileNotFoundError:
        with open(filepath, "w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(FIELDNAMES)


def write_records(records: list) -> None:
    with open(CSV_FILENAME, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        for rec in records:
            writer.writerow([rec.get(col) or "" for col in FIELDNAMES])


def run() -> None:
    ensure_header(CSV_FILENAME)

    total_days   = (LAST_DAY - STARTING_DAY).days + 1
    skipped      = []
    current_day  = STARTING_DAY

    with tqdm(total=total_days, desc="Fetching OASA data", unit="day") as pbar:
        while current_day <= LAST_DAY:
            chunk_end = min(current_day + timedelta(days=CHUNK_SIZE - 1), LAST_DAY)
            records   = get_ridership_data(current_day, chunk_end)

            if records:
                write_records(records)
            else:
                skipped.append((current_day.date(), chunk_end.date()))

            days_in_chunk = (chunk_end - current_day).days + 1
            pbar.update(days_in_chunk)
            current_day = chunk_end + timedelta(days=1)

    print(f"\nDone. Output: {CSV_FILENAME}")
    if skipped:
        print(f"Skipped {len(skipped)} chunk(s) due to persistent errors:")
        for s, e in skipped:
            print(f"  {s} – {e}")


if __name__ == "__main__":
    run()