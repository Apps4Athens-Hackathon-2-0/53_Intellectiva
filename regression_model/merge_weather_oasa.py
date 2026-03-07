import pandas as pd

print("Loading OASA data...")
oasa = pd.read_csv("oasa_raw_data.csv", low_memory=False)

print("Loading weather data...")
weather = pd.read_csv("weather_athens_hourly.csv")

print("Normalizing timestamps...")
oasa["date_hour"] = pd.to_datetime(oasa["date_hour"], errors="coerce").dt.floor("h")
weather["date_hour"] = pd.to_datetime(weather["date"], errors="coerce").dt.floor("h")
weather = weather.drop(columns=["date"])

print("Removing duplicate weather hours...")
weather = weather.drop_duplicates(subset=["date_hour"])

print(f"OASA rows: {len(oasa):,}")
print(f"Weather unique hours: {len(weather):,}")

print("Merging datasets...")
merged = oasa.merge(weather, on="date_hour", how="left")

print(f"Merged rows: {len(merged):,}")

print("Saving merged dataset...")
merged.to_csv("oasa_weather_enriched.csv", index=False)
print("Done. Saved as oasa_weather_enriched.csv")
