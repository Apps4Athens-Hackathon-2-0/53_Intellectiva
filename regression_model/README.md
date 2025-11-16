# Athens Subway Ridership Forecasting Pipeline

This repository contains a complete data engineering and machine-learning pipeline for forecasting passenger validations in the Athens Metro (Line C) using OASA ridership data and hourly weather information.

The project automates data ingestion, cleaning, enrichment, feature engineering, model training, validation, and visualization.

---

## Pipeline Overview

### 1. `fetchoasa.py`

Fetches all available OASA validations (embarking/disembarking).

* Normalizes `None` values to empty strings
* Exports `oasa_raw_data.csv`

---

### 2. `fetchweather.py`

Downloads hourly Athens weather data from:
2020-08-08 → 2025-11-13
Outputs `weather_athens_hourly.csv`

---

### 3. `merge_weather_oasa.py`

Merges OASA ridership data with hourly weather data.

* Performs timestamp alignment
* Cleans and normalizes merged fields
* Outputs `oasa_weather_enriched.csv`
  (File name may require renaming depending on script configuration.)

---

## DV Agency Reference Table

| dv_agency | dv_agency_desc |
| --------: | -------------- |
|         1 | ΟΣΥ            |
|         1 | NULL           |
|         2 | ΓΡΑΜΜΉ 1       |
|         2 | ΓΡΑΜΜΉ 3       |
|         2 | ΓΡΑΜΜΉ 2       |
|         2 | NULL           |
|         3 | ΠΡΟΑΣΤΙΑΚΟΣ    |
|         3 | NULL           |
|         4 | ΤΡΑΜ           |
|         4 | NULL           |

Only entries with `dv_agency = 2` (Subway) are used in the modeling workflow.

---

### 4. `filter_line_c.py`

Filters and cleans merged data.

* Keeps only Subway entries (`dv_agency = 2`)
* Retains only stations belonging to Line C
  Outputs `subway_c.csv`

---

### 5. `printstationdata.py`

Displays a clean, formatted summary of all available station-level data.
Useful for quick exploration and dataset verification.

---

### 6. `add_features.py`

Adds engineered features such as:

* `is_Holiday`
* `is_Weekend`
* Time-based features (`hour`, `day_of_week`, etc.)

Exports `subway_forecast_ready.csv`

---

### 7. `train_model.py`

Trains the predictive model using the enriched dataset.
Includes all feature-engineered variables.

---

### 8. `validate.py`

Evaluates model performance on validation data.
Prints accuracy metrics and diagnostic outputs.

---

### 9. `predict.py`

Provides a `Predictor` class for:

* Running trained model inference
* Generating predictions
* Performing programmatic validation

---

### 10. `plot.py`

Generates plots comparing:

* Actual average daily validations
* Predicted average daily validations

for a selected Line C station.

---

## Output File Summary

| Step                | Output File                 |
| ------------------- | --------------------------- |
| OASA data fetch     | `oasa_raw_data.csv`         |
| Weather fetch       | `weather_athens_hourly.csv` |
| Merge               | `oasa_weather_enriched.csv` |
| Filter Line C       | `subway_c.csv`              |
| Feature Engineering | `subway_forecast_ready.csv` |

---

## Requirements

Install dependencies:

```bash
pip install -r requirements.txt
```

---

## Usage

Run the pipeline step-by-step:

```bash
python fetchoasa.py
python fetchweather.py
python merge_weather_oasa.py
python filter_line_c.py
python add_features.py
python train_model.py
python validate.py
```

Plot predictions:

```bash
python plot.py
```

---

## Project Goals

* Predict hourly ridership for Athens Metro Line C
* Quantify the impact of weather conditions on subway validations
* Provide reliable forecasting tools for transport planning
* Generate interpretable visual and statistical insights
