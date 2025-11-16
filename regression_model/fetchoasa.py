import requests
import csv
from datetime import datetime, timedelta
from tqdm import tqdm

RIDERSHIP_API = "https://data.gov.gr/api/v1/query/oasa_ridership"

# Defining the range of dates to scrape
STARTING_DAY = datetime(2020, 8, 8)
LAST_DAY = datetime(2025, 11, 13)
CHUNK_SIZE = 5

CSV_FILENAME = "oasa_raw_data.csv"

# Pull data for a small date range
def get_ridership_data(from_date, to_date):
    params = {
        "date_from": from_date.strftime("%Y-%m-%d"),
        "date_to": to_date.strftime("%Y-%m-%d")
    }

    try:
        response = requests.get(RIDERSHIP_API, params=params, timeout=30)
        response.raise_for_status()
        result = response.json()

        # Occasionally the API returns a dict with an error message instead of a list
        if isinstance(result, dict) and "message" in result:
            print("Server says:", result)
            return []

        return result

    except Exception as err:
        print("Something went wrong fetching data:", err)
        return []

# This one helps convert None into something CSV can handle
def safe_str(value):
    return "" if value is None else value

def maybe_write_header(filepath):
    fieldnames = [
        "dv_agency",
        "dv_platenum_station",
        "dv_validations",
        "dv_route",
        "routes_per_hour",
        "load_dt",
        "date_hour",
        "etl_extraction_dt",
        "etl_load_dt",
        "dv_agency_desc",
        "boarding_disembark_desc"
    ]

    try:
        with open(filepath, "r", newline="", encoding="utf-8") as f:
            pass  # File exists, so nothing to do
    except FileNotFoundError:
        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(fieldnames)

def write_data_to_csv(records):
    with open(CSV_FILENAME, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        for rec in records:
            writer.writerow([
                safe_str(rec.get("dv_agency")),
                safe_str(rec.get("dv_platenum_station")),
                safe_str(rec.get("dv_validations")),
                safe_str(rec.get("dv_route")),
                safe_str(rec.get("routes_per_hour")),
                safe_str(rec.get("load_dt")),
                safe_str(rec.get("date_hour")),
                safe_str(rec.get("etl_extraction_dt")),
                safe_str(rec.get("etl_load_dt")),
                safe_str(rec.get("dv_agency_desc")),
                safe_str(rec.get("boarding_disembark_desc"))
            ])

def run():
    maybe_write_header(CSV_FILENAME)

    current_day = STARTING_DAY

    total_days = (LAST_DAY - STARTING_DAY).days
    progress = tqdm(total=total_days, desc="Scraping OASA data")

    while current_day <= LAST_DAY:
        chunk_end_day = min(current_day + timedelta(days=CHUNK_SIZE - 1), LAST_DAY)

        records = get_ridership_data(current_day, chunk_end_day)

        if records:
            write_data_to_csv(records)

        progress.update((chunk_end_day - current_day).days + 1)

        current_day = chunk_end_day + timedelta(days=1)

    progress.close()
    print("All done! Saved to:", CSV_FILENAME)

if __name__ == "__main__":
    run()
