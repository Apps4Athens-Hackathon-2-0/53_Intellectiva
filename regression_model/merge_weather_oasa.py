from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    col, to_timestamp, date_trunc, exp, lit,
    least, greatest, abs as spark_abs
)

# sparky
spark = SparkSession.builder \
    .appName("OASA_Weather_Merge") \
    .config("spark.sql.session.timeZone", "Europe/Athens") \
    .config("spark.driver.memory", "4g") \
    .config("spark.executor.memory", "4g") \
    .getOrCreate()

print("Spark session started.")

# datasets
print("Loading OASA data...")
oasa = spark.read.csv(
    "oasa_raw_data.csv",
    header=True,
    inferSchema=True
)

print("Loading weather data...")
weather = spark.read.csv(
    "weather_athens_hourly.csv",
    header=True,
    inferSchema=True
)

# timestamps to hourly
print("Normalizing timestamps...")

oasa = oasa.withColumn("date_hour", to_timestamp("date_hour"))
oasa = oasa.withColumn("date_hour", date_trunc("hour", col("date_hour")))

weather = weather.withColumn("date_hour", to_timestamp("date"))
weather = weather.withColumn("date_hour", date_trunc("hour", col("date_hour")))
weather = weather.drop("date")

# duplicate weather hours
print("Removing duplicate weather hours...")
weather = weather.dropDuplicates(["date_hour"])

# counts before merge
oasa_count = oasa.count()
weather_count = weather.count()

print(f"OASA rows: {oasa_count:,}")
print(f"Weather unique hours: {weather_count:,}")

# Merge
print("Merging datasets...")
merged = oasa.join(weather, on="date_hour", how="left")

# Compute weather score
print("Computing weather score...")

rain_factor = 1 / (1 + exp(-1.2 * (col("precipitation") - lit(1))))
cloud_factor = col("cloud_cover") / 100
temp_penalty = spark_abs(col("temperature_2m") - 22) / 22
wind_penalty = least(col("wind_speed_10m") / 40, lit(1))

raw_score = (
    1
    - 0.55 * rain_factor
    - 0.20 * cloud_factor
    - 0.15 * temp_penalty
    - 0.10 * wind_penalty
)

merged = merged.withColumn(
    "weather_score",
    least(greatest(raw_score * 100, lit(0)), lit(100))
)

# row counts after merge
merged_count = merged.count()
print(f"Merged rows: {merged_count:,}")

if merged_count != oasa_count:
    print(f"WARNING: Row count mismatch. Expected {oasa_count:,}, got {merged_count:,}")
else:
    print("Row counts match.")

# enriched dataset
print("Saving merged dataset...")

merged.coalesce(1).write.csv(
    "oasa_weather_enriched",
    header=True,
    mode="overwrite"
)

print("Done.")
print("CSV: oasa_weather_enriched/")

spark.stop()
print("Spark session stopped.")