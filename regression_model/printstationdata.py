from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    col, avg, stddev, count, when, covar_samp,
    lag, unix_timestamp
)
from pyspark.sql.window import Window
from functools import reduce

spark = SparkSession.builder \
    .appName("FilteredSubwayStationAnalysis") \
    .getOrCreate()

print("Spark session started.\n")

# Load filtered CSV
print("Loading filtered subway dataset...")
df = spark.read.csv(
    "subway_c.csv",
    header=True,
    inferSchema=True
)

total_rows = df.count()
print(f"Total rows loaded: {total_rows}\n")

df.printSchema()

# Verify subway entries
agency_check = df.select("dv_agency").distinct().collect()
print(f"Unique agencies: {[row.dv_agency for row in agency_check]}\n")

# Show unique stations
stations = df.select("dv_platenum_station").distinct().orderBy("dv_platenum_station")
station_count = stations.count()
print(f"Total unique stations: {station_count}\n")

# Prepare numeric columns
subway_num = (
    df
    .withColumn("dv_validations_num", col("dv_validations").cast("double"))
    .withColumn("precipitation_num", col("precipitation").cast("double"))
    .withColumn("temperature_num", col("temperature_2m").cast("double"))
    .filter(col("dv_validations_num").isNotNull())
    .filter(col("dv_platenum_station").isNotNull())
)

valid_rows = subway_num.count()
print(f"Rows with valid validations: {valid_rows}\n")

# ============================================================
# NEW FEATURE:
# Average time between entries (per station)
# ============================================================

print("Computing average time gap between entries per station...\n")

windowSpec = Window.partitionBy("dv_platenum_station").orderBy("date_hour")

subway_with_lags = subway_num.withColumn(
    "prev_time",
    lag("date_hour").over(windowSpec)
)

# Convert timestamp difference into hours
subway_with_lags = subway_with_lags.withColumn(
    "time_diff_hours",
    (unix_timestamp("date_hour") - unix_timestamp("prev_time")) / 3600
)

# Aggregate per station
timegap_df = subway_with_lags.groupBy("dv_platenum_station").agg(
    avg("time_diff_hours").alias("avg_time_gap_hours")
)

# ============================================================
# Existing metrics
# ============================================================

# Counts
count_df = subway_num.groupBy("dv_platenum_station").count()

# Mean validations
avg_df = subway_num.groupBy("dv_platenum_station").agg(
    avg("dv_validations_num").alias("mean_val")
)

# Variability
var_df = subway_num.groupBy("dv_platenum_station").agg(
    avg("dv_validations_num").alias("mean"),
    stddev("dv_validations_num").alias("std")
).withColumn(
    "std_to_mean_ratio",
    when(col("mean") != 0, col("std") / col("mean")).otherwise(None)
)

# Null & zero hours
null_df = subway_num.groupBy("dv_platenum_station").agg(
    count(when(col("dv_validations").isNull(), 1)).alias("null_hours"),
    count(when(col("dv_validations_num") == 0, 1)).alias("zero_hours")
)

print("Computing weather correlations...\n")

val_stats = subway_num.groupBy("dv_platenum_station").agg(
    avg("dv_validations_num").alias("val_mean"),
    stddev("dv_validations_num").alias("val_std")
)

rain_stats = subway_num.groupBy("dv_platenum_station").agg(
    avg("precipitation_num").alias("rain_mean"),
    stddev("precipitation_num").alias("rain_std")
)

temp_stats = subway_num.groupBy("dv_platenum_station").agg(
    avg("temperature_num").alias("temp_mean"),
    stddev("temperature_num").alias("temp_std")
)

cov_df = subway_num.groupBy("dv_platenum_station").agg(
    covar_samp("dv_validations_num", "precipitation_num").alias("cov_rain"),
    covar_samp("dv_validations_num", "temperature_num").alias("cov_temp")
)

corr_input = val_stats \
    .join(rain_stats, "dv_platenum_station") \
    .join(temp_stats, "dv_platenum_station") \
    .join(cov_df, "dv_platenum_station")

corr_df = corr_input.select(
    "dv_platenum_station",
    when(
        (col("val_std") > 0) & (col("rain_std") > 0),
        col("cov_rain") / (col("val_std") * col("rain_std"))
    ).otherwise(None).alias("corr_rain"),
    when(
        (col("val_std") > 0) & (col("temp_std") > 0),
        col("cov_temp") / (col("val_std") * col("temp_std"))
    ).otherwise(None).alias("corr_temp")
)

# ============================================================
# MERGE EVERYTHING
# ============================================================

print("Merging metrics...\n")

dfs = [
    count_df, avg_df, var_df,
    null_df, corr_df,
    timegap_df   # <- NEWLY ADDED METRIC
]

def join_on_station(a, b):
    return a.join(b, on="dv_platenum_station", how="left")

merged = reduce(join_on_station, dfs)

# ============================================================
# RANKING
# ============================================================

print("Ranking stations...\n")

ranked = merged.orderBy(
    col("count").desc(),
    col("mean_val").desc(),
    col("std_to_mean_ratio").asc(),
    col("avg_time_gap_hours").asc(),   # <--- lower time gaps = busier stations
    col("null_hours").asc(),
    col("zero_hours").asc()
)

ranked.show(station_count, truncate=False)

print("\nDone.")
spark.stop()
