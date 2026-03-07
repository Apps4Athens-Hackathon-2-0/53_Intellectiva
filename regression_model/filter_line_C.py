import pandas as pd

input_path = "oasa_weather_enriched.csv"
print(f"Loading {input_path}...")
df = pd.read_csv(input_path, low_memory=False)

print(f"Total records: {len(df)}")

subway_stations = [
    "ΔΗΜΟΤΙΚΟ ΘΕΑΤΡΟ", "ΠΕΙΡΑΙΑΣ", "ΜΑΝΙΑΤΙΚΑ", "ΝΙΚΑΙΑ", "ΚΟΡΥΔΑΛΛΟΣ",
    "ΑΓΙΑ ΒΑΡΒΑΡΑ", "ΑΓΙΑ ΜΑΡΙΝΑ", "ΑΙΓΑΛΕΩ", "ΕΛΑΙΩΝΑΣ", "ΚΕΡΑΜΕΙΚΟΣ",
    "ΜΟΝΑΣΤΗΡΑΚΙ", "ΣΥΝΤΑΓΜΑ", "ΕΥΑΓΓΕΛΙΣΜOΣ", "ΜΕΓΑΡΟ ΜΟΥΣΙKΗΣ", "ΑΜΠΕΛΟΚΗΠΟΙ",
    "ΠΑΝOΡΜΟΥ", "ΚΑΤΕΧΑΚΗ", "ΕΘΝΙΚΗ ΑΜΥΝΑ", "ΧΟΛΑΡΓOΣ", "ΝΟΜΙΣΜΑTΟKΟΠΕΙΟ",
    "ΑΓΙΑ ΠΑΡΑΣKΕΥΗ", "ΧΑΛΑΝΔΡΙ", "ΔΟΥΚΙΣΣΗΣ ΠΛΑΚΕΝΤΙΑΣ", "ΠΑΛΛΗΝΗ",
    "ΠΑΙΑΝΙΑ - KΑΝTΖΑ", "ΚΟΡΩΠΙ", "ΑΕΡΟΔΡΟΜΙΟ"
]

print("Filtering for Line C Subway stations...")
subway_df = df[(df["dv_agency"] == 2) & (df["dv_platenum_station"].isin(subway_stations))]

print(f"Subway records kept: {len(subway_df)}")

output_path = "subway_c.csv"
print(f"Saving to {output_path}...")
subway_df.to_csv(output_path, index=False)
print("Done.")
