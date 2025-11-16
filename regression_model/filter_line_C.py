from pyspark.sql import SparkSession
from pyspark.sql.functions import col

# Initialize Spark session
spark = SparkSession.builder \
    .appName("Subway Data Filter") \
    .getOrCreate()

# Read the CSV file
# Replace 'input_file.csv' with your actual file path
input_path = "oasa_weather_enriched.csv"
df = spark.read.csv(input_path, header=True, inferSchema=True)

# Display schema and initial count
print("Original Schema:")
df.printSchema()
print(f"\nTotal records: {df.count()}")

# Define the list of subway stations to keep
subway_stations = [
    "ΔΗΜΟΤΙΚΟ ΘΕΑΤΡΟ", "ΠΕΙΡΑΙΑΣ", "ΜΑΝΙΑΤΙΚΑ", "ΝΙΚΑΙΑ", "ΚΟΡΥΔΑΛΛΟΣ",
    "ΑΓΙΑ ΒΑΡΒΑΡΑ", "ΑΓΙΑ ΜΑΡΙΝΑ", "ΑΙΓΑΛΕΩ", "ΕΛΑΙΩΝΑΣ", "ΚΕΡΑΜΕΙΚΟΣ",
    "ΜΟΝΑΣΤΗΡΑΚΙ", "ΣΥΝΤΑΓΜΑ", "ΕΥΑΓΓΕΛΙΣΜOΣ", "ΜΕΓΑΡΟ ΜΟΥΣΙKΗΣ", "ΑΜΠΕΛΟΚΗΠΟΙ",
    "ΠΑΝOΡΜΟΥ", "ΚΑΤΕΧΑΚΗ", "ΕΘΝΙΚΗ ΑΜΥΝΑ", "ΧΟΛΑΡΓOΣ", "ΝΟΜΙΣΜΑTΟKΟΠΕΙΟ",
    "ΑΓΙΑ ΠΑΡΑΣKΕΥΗ", "ΧΑΛΑΝΔΡΙ", "ΔΟΥΚΙΣΣΗΣ ΠΛΑΚΕΝΤΙΑΣ", "ΠΑΛΛΗΝΗ",
    "ΠΑΙΑΝΙΑ - KΑΝTΖΑ", "ΚΟΡΩΠΙ", "ΑΕΡΟΔΡΟΜΙΟ"
]

# Filter for subway data (dv_agency = 2) AND specific stations
subway_df = df.filter(
    (col("dv_agency") == 2) & 
    (col("dv_platenum_station").isin(subway_stations))
)

# Display filtered data statistics
print(f"\nSubway records: {subway_df.count()}")
print("\nSample of filtered data:")
subway_df.show(5, truncate=False)

# Export to new CSV
# Replace 'output_subway_data.csv' with your desired output path
output_path = "output_subway_c.csv"

# Write as single CSV file (coalesce to 1 partition)
subway_df.coalesce(1).write.mode("overwrite") \
    .option("header", "true") \
    .csv(output_path)

# Stop Spark session
spark.stop()