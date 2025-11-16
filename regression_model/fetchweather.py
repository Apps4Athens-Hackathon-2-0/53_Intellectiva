import openmeteo_requests
import pandas as pd
import requests_cache
from retry_requests import retry
from datetime import datetime, timedelta
from tqdm import tqdm
import csv

# LONG, LAT of Athens
LAT = 37.9838
LON = 23.7275

START = datetime(2020, 8, 8)
END = datetime(2025, 11, 13)

OUTPUT = "weather_athens_hourly.csv"

cache = requests_cache.CachedSession('.cache', expire_after=-1)
session = retry(cache, retries=5, backoff_factor=0.2)
client = openmeteo_requests.Client(session=session)

HOURLY_VARS = [
    "temperature_2m",
    "precipitation",
    "rain",
    "cloud_cover",
    "wind_speed_10m",
    "weather_code"
]

def ensure_header():
    header = ["date"] + HOURLY_VARS
    try:
        with open(OUTPUT, "r", encoding="utf-8") as f:
            pass
    except FileNotFoundError:
        with open(OUTPUT, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(header)

def fetch_month(year, month):
    start = datetime(year, month, 1)
    end = (start + timedelta(days=32)).replace(day=1) - timedelta(days=1)

    if start < START:
        start = START
    if end > END:
        end = END

    params = {
        "latitude": LAT,
        "longitude": LON,
        "start_date": start.strftime("%Y-%m-%d"),
        "end_date": end.strftime("%Y-%m-%d"),
        "hourly": ",".join(HOURLY_VARS),
        "timezone": "Europe/Athens"
    }

    responses = client.weather_api("https://archive-api.open-meteo.com/v1/archive", params=params)
    response = responses[0]

    hourly = response.Hourly()

    times = pd.date_range(
        start=pd.to_datetime(hourly.Time(), unit="s"),
        end=pd.to_datetime(hourly.TimeEnd(), unit="s"),
        freq=pd.Timedelta(seconds=hourly.Interval()),
        inclusive="left"
    )

    data = {"date": times}

    for i, var in enumerate(HOURLY_VARS):
        data[var] = hourly.Variables(i).ValuesAsNumpy()

    return pd.DataFrame(data)

def main():
    ensure_header()

    current = datetime(START.year, START.month, 1)
    end_month = datetime(END.year, END.month, 1)

    pbar = tqdm(total=((end_month.year - current.year) * 12 + (end_month.month - current.month) + 1))

    while current <= end_month:
        try:
            df = fetch_month(current.year, current.month)
            df.to_csv(OUTPUT, mode="a", header=False, index=False, encoding="utf-8")
        except Exception as e:
            print(f"Failed for {current.year}-{current.month}: {e}")

        if current.month == 12:
            current = datetime(current.year + 1, 1, 1)
        else:
            current = datetime(current.year, current.month + 1, 1)

        pbar.update(1)

    pbar.close()
    print("Weather dataset saved to:", OUTPUT)

main()
