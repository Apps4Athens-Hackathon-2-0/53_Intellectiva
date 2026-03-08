#!/usr/bin/env python3

import csv
from datetime import datetime, timedelta

import openmeteo_requests
import pandas as pd
import requests_cache
from retry_requests import retry
from tqdm import tqdm

LAT    = 37.9838
LON    = 23.7275
START  = datetime(2020, 8, 8)
END    = datetime.today()
OUTPUT = "weather_athens_hourly.csv"

HOURLY_VARS = [
    "temperature_2m",
    "precipitation",
    "rain",
    "cloud_cover",
    "wind_speed_10m",
    "weather_code",
]


def build_client() -> openmeteo_requests.Client:
    cache   = requests_cache.CachedSession(".cache", expire_after=-1)
    session = retry(cache, retries=5, backoff_factor=0.2)
    return openmeteo_requests.Client(session=session)


def ensure_header() -> None:
    try:
        open(OUTPUT, "r").close()
    except FileNotFoundError:
        with open(OUTPUT, "w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(["date"] + HOURLY_VARS)


def fetch_month(client: openmeteo_requests.Client, year: int, month: int) -> pd.DataFrame:
    start = datetime(year, month, 1)
    end   = (start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
    start = max(start, START)
    end   = min(end, END)

    params = {
        "latitude":   LAT,
        "longitude":  LON,
        "start_date": start.strftime("%Y-%m-%d"),
        "end_date":   end.strftime("%Y-%m-%d"),
        "hourly":     ",".join(HOURLY_VARS),
        "timezone":   "Europe/Athens",
    }
    response = client.weather_api(
        "https://archive-api.open-meteo.com/v1/archive", params=params
    )[0]
    hourly = response.Hourly()
    times  = pd.date_range(
        start=pd.to_datetime(hourly.Time(), unit="s"),
        end=pd.to_datetime(hourly.TimeEnd(), unit="s"),
        freq=pd.Timedelta(seconds=hourly.Interval()),
        inclusive="left",
    )
    data = {"date": times}
    for i, var in enumerate(HOURLY_VARS):
        data[var] = hourly.Variables(i).ValuesAsNumpy()
    return pd.DataFrame(data)


def main() -> None:
    ensure_header()
    client = build_client()

    current    = datetime(START.year, START.month, 1)
    end_month  = datetime(END.year, END.month, 1)
    total_months = (end_month.year - current.year) * 12 + (end_month.month - current.month) + 1

    with tqdm(total=total_months, desc="Fetching weather", unit="month") as pbar:
        while current <= end_month:
            try:
                df = fetch_month(client, current.year, current.month)
                df.to_csv(OUTPUT, mode="a", header=False, index=False, encoding="utf-8")
            except Exception as exc:
                print(f"\nFailed for {current.year}-{current.month:02d}: {exc}")

            # Advance to next month without calendar arithmetic pitfalls
            if current.month == 12:
                current = datetime(current.year + 1, 1, 1)
            else:
                current = datetime(current.year, current.month + 1, 1)
            pbar.update(1)

    print(f"Weather data saved to: {OUTPUT}")


if __name__ == "__main__":
    main()