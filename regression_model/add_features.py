#!/usr/bin/env python3
"""
Feature Engineering for Pure Forecasting
Adds only calendar features - NO lag features
Output: Ready for future predictions
"""

from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from datetime import date, timedelta

# ======================================================================
# 1. Start Spark
# ======================================================================

spark = (
    SparkSession.builder
    .appName("OASA_Pure_Forecast_Features")
    .getOrCreate()
)

print("🔵 Spark session started.")

INPUT_CSV = "subway_c.csv"
OUTPUT_CSV = "subway_forecast_ready.csv"

# ======================================================================
# 2. Load base dataset
# ======================================================================

df = spark.read.csv(INPUT_CSV, header=True, inferSchema=True)
original_count = df.count()
print(f"📥 Loaded {original_count} rows from {INPUT_CSV}")

# Ensure date_hour is timestamp
df = df.withColumn("date_hour", F.to_timestamp("date_hour"))
df = df.withColumn("local_date", F.to_date("date_hour"))

# ======================================================================
# 3. Calendar features
# ======================================================================

df = (
    df
    .withColumn("hour_of_day", F.hour("date_hour"))
    .withColumn("day_of_week", F.dayofweek("local_date"))
    .withColumn("month", F.month("local_date"))
)

# is_weekend
df = df.withColumn(
    "is_weekend",
    F.when(F.col("day_of_week").isin(1, 7), 1).otherwise(0)
)

# season
df = df.withColumn(
    "season",
    F.when(F.col("month").isin(12, 1, 2), F.lit("winter"))
     .when(F.col("month").isin(3, 4, 5), F.lit("spring"))
     .when(F.col("month").isin(6, 7, 8), F.lit("summer"))
     .otherwise(F.lit("autumn"))
)

# is_peak_hour
df = df.withColumn(
    "is_peak_hour",
    F.when(
        ((F.col("hour_of_day") >= 7) & (F.col("hour_of_day") <= 10)) |
        ((F.col("hour_of_day") >= 15) & (F.col("hour_of_day") <= 18)),
        1
    ).otherwise(0)
)

# ======================================================================
# 4. Greek holiday calendar
# ======================================================================

def build_greek_holidays(start_year=2020, end_year=2026):
    holidays = []
    
    orthodox_easter = {
        2020: date(2020, 4, 19),
        2021: date(2021, 5, 2),
        2022: date(2022, 4, 24),
        2023: date(2023, 4, 16),
        2024: date(2024, 5, 5),
        2025: date(2025, 4, 20),
        2026: date(2026, 4, 12),
    }
    
    for year in range(start_year, end_year + 1):
        easter = orthodox_easter.get(year)
        if not easter:
            continue
            
        fixed = [
            date(year, 1, 1), date(year, 1, 6), date(year, 3, 25),
            date(year, 5, 1), date(year, 8, 15), date(year, 10, 28),
            date(year, 12, 25), date(year, 12, 26),
        ]
        
        easter_related = [
            easter - timedelta(days=48),
            easter - timedelta(days=2),
            easter,
            easter + timedelta(days=1),
            easter + timedelta(days=50),
        ]
        
        august_holidays = [date(year, 8, d) for d in range(8, 16)]
        holidays.extend(fixed + easter_related + august_holidays)
    
    return sorted(set(holidays))

holiday_dates = build_greek_holidays(2020, 2026)
holiday_rows = [(d,) for d in holiday_dates]
holiday_df = spark.createDataFrame(holiday_rows, ["holiday_date"])

df = (
    df.join(holiday_df, df["local_date"] == holiday_df["holiday_date"], how="left")
    .withColumn("is_holiday", F.when(F.col("holiday_date").isNotNull(), 1).otherwise(0))
    .drop("holiday_date")
)

print(f"📅 Added {len(holiday_dates)} holiday dates")

# ======================================================================
# 5. Boarding flag
# ======================================================================

df = df.withColumn(
    "is_boarding",
    F.when(F.col("boarding_disembark_desc") == "Boarding", 1).otherwise(0)
)

# ======================================================================
# 6. Validation
# ======================================================================

final_count = df.count()
print(f"✅ Final row count: {final_count} (original: {original_count})")

if final_count != original_count:
    print(f"⚠️  Row count changed by {original_count - final_count}")
else:
    print("✨ Row count preserved exactly")

# ======================================================================
# 7. Save
# ======================================================================

print(f"\n💾 Saving to {OUTPUT_CSV}...")

(
    df
    .coalesce(1)
    .write
    .csv(OUTPUT_CSV, header=True, mode="overwrite")
)

print(f"✅ Saved: {OUTPUT_CSV}")
print("\n📋 Features added:")
print("   • hour_of_day, day_of_week, month")
print("   • is_weekend, is_holiday, is_peak_hour")
print("   • season")
print("   • is_boarding")
print("\n🎯 NO lag features - ready for pure forecasting!")

spark.stop()
print("✨ Done.")